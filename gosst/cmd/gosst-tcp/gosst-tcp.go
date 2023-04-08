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

	"github.com/blockloop/scan"
	"github.com/jessevdk/go-flags"
	"github.com/pebbe/zmq4"
	"github.com/ugorji/go/codec"
	_ "modernc.org/sqlite"

	queries "gosst/internal/db"
	psst "gosst/internal/formats/psst"
	sst "gosst/internal/formats/sst"
)

func putSession(db *sql.DB, h codec.Handle, board, name string, sst_data []byte) (int, error) {
	var setupId, linkageId, frontCalibrationId, rearCalibrationId int
	err := db.QueryRow(queries.SetupForBoard, board).Scan(&setupId, &linkageId, &frontCalibrationId, &rearCalibrationId)
	if err != nil {
		return -1, err
	}

	var linkage psst.Linkage
	rows, err := db.Query(queries.Linkage, linkageId)
	if err != nil {
		return -1, err
	}
	if err = scan.RowStrict(&linkage, rows); err != nil {
		return -1, err
	}
	if err = linkage.Process(); err != nil {
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
	BoardId [8]byte
	Size    uint64
	Name    [9]byte
}

func handleRequest(conn net.Conn, db *sql.DB, h codec.Handle, soc *zmq4.Socket) {
	bufHeader := make([]byte, 25)
	l, err := conn.Read(bufHeader)
	if err != nil || l != 25 {
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

	if id, err := putSession(db, h, hex.EncodeToString(header.BoardId[:]), name, data); err != nil {
		conn.Write([]byte{0xfa /* ERR_VAL from LwIP */})
		log.Println("[ERR] session '", name, "' could not be imported")
	} else {
		conn.Write([]byte{6 /* STATUS_SUCCESS */})
		log.Println("[OK] session '", name, "' was successfully imported")

		if soc != nil {
			b := make([]byte, 4)
			binary.LittleEndian.PutUint32(b, uint32(id))
			soc.SendBytes(b, 0)
		}
	}
}

func main() {
	var opts struct {
		DatabaseFile string `short:"d" long:"database" description:"SQLite3 database file path" required:"true"`
		Host         string `short:"h" long:"host" description:"Host to bind on" default:"0.0.0.0"`
		Port         string `short:"p" long:"port" description:"Port to bind on" default:"557"`
		ZmqHost      string `short:"H" long:"zhost" description:"ZMQ server host" default:"127.0.0.1"`
		ZmqPort      string `short:"P" long:"zport" description:"ZMQ server port" default:"5555"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	var h codec.MsgpackHandle

	db, err := sql.Open("sqlite", opts.DatabaseFile)
	if err != nil {
		log.Fatal("[ERR] could not open database")
	}
	if _, err := db.Exec(queries.Schema); err != nil {
		log.Fatal("[ERR] could not create data tables")
	}

	l, err := net.Listen("tcp", opts.Host+":"+opts.Port)
	if err != nil {
		log.Fatal("[ERR]", err.Error())
	}
	defer l.Close()

	soc, err := zmq4.NewSocket(zmq4.PUSH)
	defer soc.Close()
	if err != nil {
		log.Println("[WARN] could not create ZMQ socket (cache generation disabled)")
	} else {
		if err = soc.Connect("tcp://" + opts.ZmqHost + ":" + opts.ZmqPort); err != nil {
			log.Println("[WARN] could not connect to ZMQ server (cache generation disabled)")
			soc.Close()
			soc = nil
		}
	}

	for {
		conn, err := l.Accept()
		if err != nil {
			log.Println("[ERR]", err.Error())
			continue
		}
		go handleRequest(conn, db, &h, soc)
	}
}
