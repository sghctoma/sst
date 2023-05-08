package main

import (
	"bytes"
	"database/sql"
	"encoding/binary"
	"encoding/hex"
	"io"
	"log"
	"net"
	"net/http"
	"regexp"
	"strconv"

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

type BokehFailedError struct{}

func (e *BokehFailedError) Error() string {
	return "Bokeh generator failed"
}

func initiateBokehGeneration(url string) error {
	req, err := http.NewRequest("PUT", url, bytes.NewBuffer([]byte{}))
	if err != nil {
		return err
	}
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 204 {
		return &BokehFailedError{}
	}
	return nil
}

func getLinkage(db *sql.DB, id int) (*psst.Linkage, error) {
	var linkage psst.Linkage
	rows, err := db.Query(queries.Linkage, id)
	if err != nil {
		return nil, err
	}
	if err = scan.RowStrict(&linkage, rows); err != nil {
		return nil, err
	}
	if err = linkage.ProcessRawData(); err != nil {
		return nil, err
	}

	return &linkage, nil
}

func getCalibration(db *sql.DB, id int, maxStroke, maxTravel float64) (*psst.Calibration, error) {
	var calibration psst.Calibration
	rows, err := db.Query(queries.Calibration, id)
	if err != nil {
		return nil, err
	}
	if err = scan.RowStrict(&calibration, rows); err != nil {
		return nil, err
	}
	if err := calibration.ProcessRawInputs(); err != nil {
		return nil, err
	}
	rows, err = db.Query(queries.CalibrationMethod, calibration.MethodId)
	if err != nil {
		return nil, err
	}
	calibration.Method = new(psst.CalibrationMethod)
	if err = scan.RowStrict(calibration.Method, rows); err != nil {
		return nil, err
	}
	if err = calibration.Method.ProcessRawData(); err != nil {
		return nil, err
	}
	if err = calibration.Prepare(maxStroke, maxTravel); err != nil {
		return nil, err
	}

	return &calibration, nil
}

func putSessionWithSetup(db *sql.DB, h codec.Handle, board [10]byte, name string, sst_data []byte) (int, error) {
	var setupId, linkageId, frontCalibrationId, rearCalibrationId int
	setupId = int(binary.LittleEndian.Uint32(board[6:]))
	err := db.QueryRow(queries.Setup, setupId).Scan(&linkageId, &frontCalibrationId, &rearCalibrationId)
	if err != nil {
		return -1, err
	}

	linkage, err := getLinkage(db, linkageId)
	if err != nil {
		return -1, nil
	}

	frontCalibration, err := getCalibration(db, frontCalibrationId, linkage.MaxFrontStroke, linkage.MaxFrontTravel)
	if err != nil {
		return -1, nil
	}

	rearCalibration, err := getCalibration(db, rearCalibrationId, linkage.MaxRearStroke, linkage.MaxRearTravel)
	if err != nil {
		return -1, nil
	}

	front, rear, meta, err := sst.ProcessRaw(sst_data)
	if err != nil {
		return -1, err
	}
	meta.Name = name
	pd, err := psst.ProcessRecording(front, rear, meta, *linkage, *frontCalibration, *rearCalibration)
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

func putSessionWithBoard(db *sql.DB, h codec.Handle, board [10]byte, name string, sst_data []byte) (int, error) {
	var setupId, linkageId, frontCalibrationId, rearCalibrationId int
	boardId := hex.EncodeToString(board[2:])
	err := db.QueryRow(queries.SetupForBoard, boardId).Scan(&setupId, &linkageId, &frontCalibrationId, &rearCalibrationId)
	if err != nil {
		// Store unknown ID, so that it can be picked up from the UI
		db.QueryRow(queries.InsertBoard, boardId, nil)
		return -1, &NoSuchBoardError{boardId}
	}

	linkage, err := getLinkage(db, linkageId)
	if err != nil {
		return -1, nil
	}

	frontCalibration, err := getCalibration(db, frontCalibrationId, linkage.MaxFrontStroke, linkage.MaxFrontTravel)
	if err != nil {
		return -1, nil
	}

	rearCalibration, err := getCalibration(db, rearCalibrationId, linkage.MaxRearStroke, linkage.MaxRearTravel)
	if err != nil {
		return -1, nil
	}

	front, rear, meta, err := sst.ProcessRaw(sst_data)
	if err != nil {
		return -1, err
	}
	meta.Name = name
	pd, err := psst.ProcessRecording(front, rear, meta, *linkage, *frontCalibration, *rearCalibration)
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
		id, err = putSessionWithBoard(db, h, header.BoardId, name, data)
	} else if string(header.BoardId[:6]) == "SETUP_" {
		id, err = putSessionWithSetup(db, h, header.BoardId, name, data)
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

		url := server + "/api/session/" + strconv.Itoa(id) + "/bokeh"
		if err := initiateBokehGeneration(url); err != nil {
			log.Println("[WARN] could not initiate Bokeh component generation", err)
		}
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
