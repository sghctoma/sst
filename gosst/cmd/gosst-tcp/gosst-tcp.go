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
	"github.com/ugorji/go/codec"
	_ "modernc.org/sqlite"

	psst "gosst/internal/psst"
	schema "gosst/internal/schema"
)

func putSession(db *sql.DB, h codec.Handle, board, name string, sst []byte) error {
	var setupId, linkageId, frontCalibrationId, rearCalibrationId int
	q := `SELECT S.setup_id, S.linkage_id, S.front_calibration_id, S.rear_calibration_id
		  FROM setups S JOIN boards B
          WHERE
		    B.board_id = ? AND
            S.setup_id = B.setup_id;`
	err := db.QueryRow(q, board).Scan(&setupId, &linkageId, &frontCalibrationId, &rearCalibrationId)
	if err != nil {
		return err
	}

	var linkage psst.Linkage
	rows, err := db.Query("SELECT * FROM linkages WHERE linkage_id = ?", linkageId)
	if err != nil {
		return err
	}
	err = scan.RowStrict(&linkage, rows)
	if err != nil {
		return err
	}
	err = linkage.Process()
	if err != nil {
		return err
	}

	var frontCalibration psst.Calibration
	rows, err = db.Query("SELECT * FROM calibrations WHERE calibration_id = ?", frontCalibrationId)
	if err != nil {
		return err
	}
	err = scan.RowStrict(&frontCalibration, rows)
	if err != nil {
		return err
	}

	var rearCalibration psst.Calibration
	rows, err = db.Query("SELECT * FROM calibrations WHERE calibration_id = ?", rearCalibrationId)
	if err != nil {
		return err
	}
	err = scan.RowStrict(&rearCalibration, rows)
	if err != nil {
		return err
	}

	pd := psst.ProcessRecording(sst, name, linkage, frontCalibration, rearCalibration)

	var data []byte
	enc := codec.NewEncoderBytes(&data, h)
	enc.Encode(pd)
	if _, err := db.Exec("INSERT INTO sessions (name, timestamp, description, setup_id, data) VALUES (?, ?, ?, ?, ?)",
		name, pd.Timestamp, "", setupId, data); err != nil {

		return err
	}

	return nil
}

type header struct {
	BoardId [8]byte
	Size    uint64
	Name    [9]byte
}

func handleRequest(conn net.Conn, db *sql.DB, h codec.Handle) {
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

	if putSession(db, h, hex.EncodeToString(header.BoardId[:]), name, data) == nil {
		conn.Write([]byte{6 /* STATUS_SUCCESS */})
		log.Print("[OK] session '", name, "' was successfully imported")
	} else {
		conn.Write([]byte{0xfa /* ERR_VAL from LwIP */})
		log.Print("[ERR] session '", name, "' could not be imported")
	}
}

func main() {
	var opts struct {
		DatabaseFile string `short:"d" long:"database" description:"SQLite3 database file path" required:"true"`
		Host         string `short:"h" long:"host" description:"Host to bind on" default:"0.0.0.0"`
		Port         string `short:"p" long:"port" description:"Port to bind on" default:"557"`
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
	if _, err := db.Exec(schema.Sql); err != nil {
		log.Fatal("[ERR] could not create data tables")
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
		go handleRequest(conn, db, &h)
	}
}
