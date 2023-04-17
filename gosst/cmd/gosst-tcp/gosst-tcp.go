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
	"time"

	"github.com/blockloop/scan"
	"github.com/jessevdk/go-flags"
	"github.com/ugorji/go/codec"
	_ "modernc.org/sqlite"

	psst "gosst/formats/psst"
	sst "gosst/formats/sst"
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

func putSession(db *sql.DB, h codec.Handle, board [10]byte, name string, sst_data []byte) (int, error) {
	var setupId, linkageId, frontCalibrationId, rearCalibrationId int
	if string(board[:2]) == "ID" {
		boardId := hex.EncodeToString(board[2:])
		err := db.QueryRow(queries.SetupForBoard, boardId).Scan(&setupId, &linkageId, &frontCalibrationId, &rearCalibrationId)
		if err != nil {
			return -1, &NoSuchBoardError{boardId}
		}
	} else if string(board[:6]) == "SETUP_" {
		setupId = int(binary.LittleEndian.Uint32(board[6:]))
		err := db.QueryRow(queries.Setup, setupId).Scan(&linkageId, &frontCalibrationId, &rearCalibrationId)
		if err != nil {
			return -1, err
		}
	} else {
		return -1, &InvalidBoardError{}
	}

	var linkage psst.Linkage
	rows, err := db.Query(queries.Linkage, linkageId)
	if err != nil {
		return -1, err
	}
	if err = scan.RowStrict(&linkage, rows); err != nil {
		return -1, err
	}
	if err = linkage.ProcessRawData(); err != nil {
		return -1, err
	}

	var frontCalibration psst.Calibration
	rows, err = db.Query(queries.Calibration, frontCalibrationId)
	if err != nil {
		return -1, err
	}
	if err = scan.RowStrict(&frontCalibration, rows); err != nil {
		return -1, err
	}
	if err := frontCalibration.ProcessRawInputs(); err != nil {
		return -1, err
	}
	rows, err = db.Query(queries.CalibrationMethod, frontCalibration.MethodId)
	if err != nil {
		return -1, err
	}
	frontCalibration.Method = new(psst.CalibrationMethod)
	if err = scan.RowStrict(frontCalibration.Method, rows); err != nil {
		return -1, err
	}
	if err = frontCalibration.Method.ProcessRawData(); err != nil {
		return -1, err
	}
	if err = frontCalibration.Prepare(linkage.MaxFrontStroke, linkage.MaxFrontTravel); err != nil {
		return -1, err
	}

	var rearCalibration psst.Calibration
	rows, err = db.Query(queries.Calibration, rearCalibrationId)
	if err != nil {
		return -1, err
	}
	if err = scan.RowStrict(&rearCalibration, rows); err != nil {
		return -1, err
	}
	if err := rearCalibration.ProcessRawInputs(); err != nil {
		return -1, err
	}
	rows, err = db.Query(queries.CalibrationMethod, rearCalibration.MethodId)
	if err != nil {
		return -1, err
	}
	rearCalibration.Method = new(psst.CalibrationMethod)
	if err = scan.RowStrict(rearCalibration.Method, rows); err != nil {
		return -1, err
	}
	if err = rearCalibration.Method.ProcessRawData(); err != nil {
		return -1, err
	}
	if err = rearCalibration.Prepare(linkage.MaxRearStroke, linkage.MaxRearTravel); err != nil {
		return -1, err
	}

	front, rear, meta, err := sst.ProcessRaw(sst_data)
	if err != nil {
		return -1, err
	}
	meta.Name = name
	pd, err := psst.ProcessRecording(front, rear, meta, linkage, frontCalibration, rearCalibration)
	if err != nil {
		return -1, err
	}

	var data []byte
	enc := codec.NewEncoderBytes(&data, h)
	enc.Encode(pd)

	var lastInsertedId int
	err = db.QueryRow(queries.InsertSession, name, pd.Timestamp, "", setupId, data).Scan(&lastInsertedId)
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

func handleRequest(conn net.Conn, db *sql.DB, h codec.Handle, channel chan int) {
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

	if id, err := putSession(db, h, header.BoardId, name, data); err != nil {
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

		channel <- id
	}
}

func main() {
	var opts struct {
		DatabaseFile string `short:"d" long:"database" description:"SQLite3 database file path" required:"true"`
		Host         string `short:"h" long:"host" description:"Host to bind on" default:"0.0.0.0"`
		Port         string `short:"p" long:"port" description:"Port to bind on" default:"557"`
		CacheServer  string `short:"c" long:"cache" description:"cache.py server address" default:"127.0.0.1:5555"`
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

	channel := make(chan int, 100)
	go func() {
		for {
			conn, err := net.Dial("tcp", opts.CacheServer)
			if err != nil {
				log.Println("[WARN] could not connect to server (retry in 5s)")
				time.Sleep(5 * time.Second)
				continue
			}

			for {
				id := <-channel
				b := make([]byte, 4)
				b[0] = byte(id)
				b[1] = byte(id >> 8)
				b[2] = byte(id >> 16)
				b[3] = byte(id >> 24)
				conn.Write(b)
				conn.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
				if _, err := conn.Read(b); err != nil {
					log.Println("[WARN] could not send session id to cache server!")
					channel <- id
					break
				}
			}

			conn.Close()
		}
	}()

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
		go handleRequest(conn, db, &h, channel)
	}
}
