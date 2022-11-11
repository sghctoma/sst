package main

import (
	"bytes"
	"database/sql"
	"encoding/binary"
	"io/ioutil"
	"log"
	"net"
	"os"
	"regexp"

	"github.com/ugorji/go/codec"
	_ "modernc.org/sqlite"

	psst "gosst/internal/psst"
)

type calibrationPair struct {
    Name  string      `codec:"," json:"name" binding:"required"`
    Front psst.Calibration `codec:"," json:"front" validate:"dive" binding:"required"`
    Rear  psst.Calibration `codec:"," json:"rear" validate:"dive" binding:"required"`
}

func defaultCalibration(db *sql.DB, h codec.Handle) (psst.Calibration, psst.Calibration, error) {
    var data []byte
    err := db.QueryRow("SELECT data FROM calibrations where ROWID=(SELECT ROWID FROM defaults WHERE name='calibrations')").Scan(&data)
    if err != nil {
        return psst.Calibration{}, psst.Calibration{}, nil
    }

    cdec := codec.NewDecoderBytes(data, h)
    var cpair calibrationPair
    cdec.Decode(&cpair)

    return cpair.Front, cpair.Rear, nil
}

func defaultLinkage(db *sql.DB, h codec.Handle) (psst.Linkage, error) {
    var data []byte
    err := db.QueryRow("SELECT data FROM linkages where ROWID=(SELECT ROWID FROM defaults WHERE name='linkages')").Scan(&data)
    if err != nil {
        return psst.Linkage{}, err
    }

    cdec := codec.NewDecoderBytes(data, h)
    var linkage psst.Linkage
    cdec.Decode(&linkage)

    return linkage, err
}

func putSession(db *sql.DB, h codec.Handle, name string, sst []byte) bool {
    l, err := defaultLinkage(db, h)
    if err != nil {
        return false
    }

    fcal, rcal, err := defaultCalibration(db, h)
    if err != nil {
        return false
    }

    pd := psst.ProcessRecording(sst, "", l, fcal, rcal)

    var data []byte
    enc := codec.NewEncoderBytes(&data, h)
    enc.Encode(pd)
    if _, err := db.Exec("INSERT INTO sessions VALUES (?, ?, ?, ?)", name, "", pd.Timestamp, data); err != nil {
        return false
    }

    log.Print("[OK] session '", name, "' was successfully imported")

    return true
}

func handleRequest(conn net.Conn, db *sql.DB, h codec.Handle) {
    bufHeader := make([]byte, 18)
    l, err := conn.Read(bufHeader)
    if err != nil || l != 18 {
        return
    }
    defer conn.Close()

    reader := bytes.NewReader(bufHeader)
    var size uint64
    err = binary.Read(reader, binary.LittleEndian, &size)
    if err != nil || size > 32*1024*1024 {
        log.Println("[ERR] Invalid data")
        return
    }

    name := string(bufHeader[8:])
    if m, _ := regexp.MatchString("[0-9]{5}\\.SST", name); !m {
        log.Println("[ERR] Invalid data")
        return
    }

    bufData, err := ioutil.ReadAll(conn)
    if err != nil {
        log.Println("[ERR]", err)
        return
    }

    putSession(db, h, name, bufData)
}

func main() {
    var h codec.MsgpackHandle

    db, err := sql.Open("sqlite", os.Args[1])
    if err != nil {
        log.Fatal("[ERR] could not open database")
    }
    if _, err := db.Exec(`
            CREATE TABLE IF NOT EXISTS calibrations(data BLOB);
            CREATE TABLE IF NOT EXISTS linkages(data BLOB);
            CREATE TABLE IF NOT EXISTS defaults(name TEXT, id INTEGER);
            CREATE TABLE IF NOT EXISTS sessions(name TEXT, description TEXT, date INTEGER, data BLOB);`); err != nil {
        log.Fatal("[ERR] could not create data tables")
    }

    l, err := net.Listen("tcp", ":1557")
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
