package common

import (
	"bytes"
	"database/sql"
	"log"
	"net/http"
	"reflect"
	"strings"

	"github.com/blockloop/scan"
	"github.com/google/uuid"
	"github.com/ugorji/go/codec"
	_ "modernc.org/sqlite"

	psst "gosst/formats/psst"
	queries "gosst/internal/db"
)

type UuidExt struct{}

func (x UuidExt) WriteExt(v interface{}) []byte {
	v2 := v.(*uuid.UUID)
	return []byte(v2.String())
}

func (x UuidExt) ReadExt(dst interface{}, src []byte) {
	tt := dst.(*uuid.UUID)
	*tt = uuid.MustParse(string(src))
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

func GetLinkage(db *sql.DB, id uuid.UUID) (*psst.Linkage, error) {
	var linkage psst.Linkage
	linkageId := strings.ReplaceAll(id.String(), "-", "")
	rows, err := db.Query(queries.Linkage, linkageId)
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

func getCalibration(db *sql.DB, id uuid.UUID, maxStroke, maxTravel float64) (*psst.Calibration, error) {
	var calibration psst.Calibration
	calibrationId := strings.ReplaceAll(id.String(), "-", "")
	rows, err := db.Query(queries.Calibration, calibrationId)
	if err != nil {
		return nil, err
	}
	if err = scan.RowStrict(&calibration, rows); err != nil {
		return nil, err
	}
	if err := calibration.ProcessRawInputs(); err != nil {
		return nil, err
	}

	calibrationMethodId := strings.ReplaceAll(calibration.MethodId.String(), "-", "")
	rows, err = db.Query(queries.CalibrationMethod, calibrationMethodId)
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

func GetSetupsForIds(db *sql.DB, linkageUuid, frontCalibrationUuid, rearCalibrationUuid uuid.UUID) (*psst.SetupData, error) {

	linkage, err := GetLinkage(db, linkageUuid)
	if err != nil {
		return nil, err
	}

	frontCalibration, err := getCalibration(db, frontCalibrationUuid, linkage.MaxFrontStroke, linkage.MaxFrontTravel)
	if err != nil {
		return nil, err
	}

	rearCalibration, err := getCalibration(db, rearCalibrationUuid, linkage.MaxRearStroke, linkage.MaxRearTravel)
	if err != nil {
		return nil, err
	}

	return &psst.SetupData{
		Linkage:          linkage,
		FrontCalibration: frontCalibration,
		RearCalibration:  rearCalibration,
	}, err
}

func InsertSession(db *sql.DB, newUuid uuid.UUID, pd *psst.Processed, server, name, description string, setupUuid uuid.UUID) error {
	var data []byte
	var h codec.MsgpackHandle
	h.SetBytesExt(reflect.TypeOf(uuid.UUID{}), 1, UuidExt{})
	enc := codec.NewEncoderBytes(&data, &h)
	enc.Encode(pd)

	newId := strings.ReplaceAll(newUuid.String(), "-", "")
	setupId := strings.ReplaceAll(setupUuid.String(), "-", "")
	_, err := db.Query(queries.InsertSession, newId, name, pd.Timestamp, description, setupId, data)
	if err != nil {
		return err
	}

	url := server + "/api/session/" + newUuid.String() + "/bokeh"
	if err := initiateBokehGeneration(url); err != nil {
		log.Println("[WARN] could not initiate Bokeh component generation", err)
	}

	return nil
}
