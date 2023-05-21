package main

import (
	"bytes"
	"encoding/binary"
	"io"
	"log"
	"net"
	"regexp"

	"github.com/jessevdk/go-flags"
)

type header struct {
	BoardId [10]byte
	Size    uint64
	Name    [9]byte
}

func handleRequest(conn net.Conn) {
	bufHeader := make([]byte, 27)
	l, err := conn.Read(bufHeader)
	if err != nil || l != 27 {
		log.Println("[ERR] Could not fetch header")
		conn.Write([]byte{0xf1 /* ERR_CLSD from LwIP */})
		return
	}
	defer conn.Close()

	reader := bytes.NewReader(bufHeader)
	var header header
	err = binary.Read(reader, binary.LittleEndian, &header)
	if err != nil {
		log.Println("[ERR] Invalid data")
		conn.Write([]byte{0xfa /* ERR_VAL from LwIP */})
		return
	}

	if string(header.BoardId[2:]) == "XXXXXXXX" {
		log.Println("[ERR] Invalid data")
		conn.Write([]byte{0xfa /* ERR_VAL from LwIP */})
		return
	}

	if header.Size > 32*1024*1024 {
		log.Println("[ERR] Size exceeds maximum")
		conn.Write([]byte{0xfa /* ERR_VAL from LwIP */})
		return
	}

	name := string(header.Name[:])
	if m, _ := regexp.MatchString("[0-9]{5}\\.SST", name); !m {
		log.Println("[ERR] Wrong name format")
		conn.Write([]byte{0xfa /* ERR_VAL from LwIP */})
		return
	}
	conn.Write([]byte{4 /* STATUS_HEADER_OK */})

	data := make([]byte, header.Size)
	_, err = io.ReadFull(conn, data)
	if err != nil {
		log.Println("[ERR] Could not fetch data")
		conn.Write([]byte{0xf1 /* ERR_CLSD from LwIP */})
		return
	}

	conn.Write([]byte{6 /* STATUS_SUCCESS */})
	log.Println("[OK] session '", name, "' was successfully imported")
	// send back a dummy id
	// XXX check to see if DAQ unit not reading it is a problem
	id := 1337
	b := make([]byte, 4)
	b[0] = byte(id)
	b[1] = byte(id >> 8)
	b[2] = byte(id >> 16)
	b[3] = byte(id >> 24)
	conn.Write(b)
}

func main() {
	var opts struct {
		Host string `short:"h" long:"host" description:"Host to bind on" default:"0.0.0.0"`
		Port string `short:"p" long:"port" description:"Port to bind on" default:"1557"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	l, err := net.Listen("tcp", opts.Host+":"+opts.Port)
	if err != nil {
		log.Fatal("[ERR]", err.Error())
	}
	defer l.Close()

	for {
		conn, err := l.Accept()
		if err != nil {
			log.Println("[ERR]", err.Error())
			continue
		}
		go handleRequest(conn)
	}
}
