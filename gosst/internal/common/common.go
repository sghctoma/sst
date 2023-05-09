package common

import (
	"bytes"
	"database/sql"
	"log"
	"net/http"
	"strconv"

	"github.com/blockloop/scan"
	"github.com/ugorji/go/codec"
	_ "modernc.org/sqlite"

	psst "gosst/formats/psst"
	queries "gosst/internal/db"
)

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

func GetLinkage(db *sql.DB, id int) (*psst.Linkage, error) {
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

func GetSetupsForIds(db *sql.DB, linkageId, frontCalibrationId, rearCalibrationId int) (*psst.SetupData, error) {
	linkage, err := GetLinkage(db, linkageId)
	if err != nil {
		return nil, err
	}

	frontCalibration, err := getCalibration(db, frontCalibrationId, linkage.MaxFrontStroke, linkage.MaxFrontTravel)
	if err != nil {
		return nil, err
	}

	rearCalibration, err := getCalibration(db, rearCalibrationId, linkage.MaxRearStroke, linkage.MaxRearTravel)
	if err != nil {
		return nil, err
	}

	return &psst.SetupData{
		Linkage:          linkage,
		FrontCalibration: frontCalibration,
		RearCalibration:  rearCalibration,
	}, err
}

func InsertSession(db *sql.DB, pd *psst.Processed, server, name, description string, setupId int) (int, error) {
	var data []byte
	var h codec.MsgpackHandle
	enc := codec.NewEncoderBytes(&data, &h)
	enc.Encode(pd)

	var lastInsertedId int
	err := db.QueryRow(queries.InsertSession, name, pd.Timestamp, description, setupId, data).Scan(&lastInsertedId)
	if err != nil {
		return 0, err
	}

	url := server + "/api/session/" + strconv.Itoa(lastInsertedId) + "/bokeh"
	if err := initiateBokehGeneration(url); err != nil {
		log.Println("[WARN] could not initiate Bokeh component generation", err)
	}

	return lastInsertedId, nil
}
