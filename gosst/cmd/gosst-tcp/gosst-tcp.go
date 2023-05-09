package main

import (
	"bytes"
	"database/sql"
	"encoding/binary"
	"encoding/hex"
	"io"
	"log"
	"net"
	"regexp"

	"github.com/jessevdk/go-flags"
	"github.com/ugorji/go/codec"
	_ "modernc.org/sqlite"

	psst "gosst/formats/psst"
	sst "gosst/formats/sst"
	common "gosst/internal/common"
	queries "gosst/internal/db"
)

type NoSuchBoardError struct {
	board string
}

func (e *NoSuchBoardError) Error() string {
	return "board with id \"" + e.board + "\" was not found"
}

type InvalidBoardError struct{}

func (e *InvalidBoardError) Error() string {
	return "received malformed board id"
}

func putSession(db *sql.DB, h codec.Handle, board [10]byte, server, name string, sst_data []byte) (int, error) {
	var setupId, linkageId, frontCalibrationId, rearCalibrationId int
	boardId := hex.EncodeToString(board[2:])
	err := db.QueryRow(queries.SetupForBoard, boardId).Scan(&setupId, &linkageId, &frontCalibrationId, &rearCalibrationId)
	if err != nil {
		// Store unknown ID, so that it can be picked up from the UI
		db.QueryRow(queries.InsertBoard, boardId, nil)
		return -1, &NoSuchBoardError{boardId}
	}

	setup, err := common.GetSetupsForIds(db, linkageId, frontCalibrationId, rearCalibrationId)
	if err != nil {
		return -1, err
	}

	front, rear, meta, err := sst.ProcessRaw(sst_data)
	if err != nil {
		return -1, err
	}
	meta.Name = name
	pd, err := psst.ProcessRecording(front, rear, meta, setup)
	if err != nil {
		return -1, err
	}

	lastInsertedId, err := common.InsertSession(db, pd, server, name, "Imported from "+name, setupId)
	if err != nil {
		return -1, err
	}

	return lastInsertedId, nil
}

type header struct {
	BoardId [10]byte
	Size    uint64
	Name    [9]byte
}

func handleRequest(conn net.Conn, db *sql.DB, server string, h codec.Handle) {
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

	var id int
	if string(header.BoardId[:2]) == "ID" {
		id, err = putSession(db, h, header.BoardId, server, name, data)
	} else {
		err = &InvalidBoardError{}
	}
	if err != nil {
		conn.Write([]byte{0xfa /* ERR_VAL from LwIP */})
		log.Println("[ERR] session '", name, "' could not be imported:", err)
	} else {
		conn.Write([]byte{6 /* STATUS_SUCCESS */})
		log.Println("[OK] session '", name, "' was successfully imported")
		// send back the id for the new session
		// XXX check to see if DAQ unit not reading it is a problem
		b := make([]byte, 4)
		b[0] = byte(id)
		b[1] = byte(id >> 8)
		b[2] = byte(id >> 16)
		b[3] = byte(id >> 24)
		conn.Write(b)
	}
}

func main() {
	var opts struct {
		DatabaseFile string `short:"d" long:"database" description:"SQLite3 database file path" required:"true"`
		Host         string `short:"h" long:"host" description:"Host to bind on" default:"0.0.0.0"`
		Port         string `short:"p" long:"port" description:"Port to bind on" default:"557"`
		ApiServer    string `short:"s" long:"server" description:"HTTP API server" default:"http://localhost:5000"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	var h codec.MsgpackHandle

	db, err := sql.Open("sqlite", opts.DatabaseFile)
	if err != nil {
		log.Fatalln("[ERR] could not open database")
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
		go handleRequest(conn, db, opts.ApiServer, &h)
	}
}
