package main

import (
	"encoding/json"
	"log"
	"os"
	"path"
	"reflect"
	"strings"

	"github.com/google/uuid"
	"github.com/jessevdk/go-flags"
	"github.com/ugorji/go/codec"

	psst "gosst/formats/psst"
	sst "gosst/formats/sst"
	common "gosst/internal/common"
)

func main() {
	var opts struct {
		TelemetryFile string `short:"t" long:"telemetry" description:"Telemetry data file (.SST)" required:"true"`
		Linkage       string `short:"l" long:"linkage" description:"Linkage data file (JSON)" required:"true"`
		Calibration   string `short:"c" long:"calibration" description:"Calibration data file (JSON)" required:"true"`
		OutputFile    string `short:"o" long:"output" description:"Output file"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	l, err := os.ReadFile(opts.Linkage)
	if err != nil {
		log.Fatalln(err)
	}
	var linkage psst.Linkage
	if err := json.Unmarshal(l, &linkage); err != nil {
		log.Fatalln(err)
	}
	if err := linkage.ProcessRawData(); err != nil {
		log.Fatalln(err)
	}

	c, err := os.ReadFile(opts.Calibration)
	if err != nil {
		log.Fatalln(err)
	}
	fcal, rcal, err := psst.LoadCalibrations(c, linkage)
	if err != nil {
		log.Fatalln(err)
	}

	tb, err := os.ReadFile(opts.TelemetryFile)
	if err != nil {
		log.Fatalln(err)
	}

	front, rear, meta, err := sst.ProcessRaw(tb)
	if err != nil {
		log.Fatalln(err)
	}
	meta.Name = opts.TelemetryFile
	setup := psst.SetupData{
		Linkage:          &linkage,
		FrontCalibration: fcal,
		RearCalibration:  rcal,
	}
	pd, err := psst.ProcessRecording(front, rear, meta, &setup)
	if err != nil {
		log.Fatalln(err)
	}

	var output = opts.OutputFile
	if output == "" {
		ext := path.Ext(opts.TelemetryFile)
		if ext == "" {
			output = opts.TelemetryFile + ".PSST"
		} else {
			n := strings.LastIndex(opts.TelemetryFile, ext)
			output = opts.TelemetryFile[:n] + ".PSST"
		}
	}
	fo, err := os.Create(output)
	if err != nil {
		log.Fatalln(err)
	}
	defer fo.Close()

	var h codec.MsgpackHandle
	h.SetBytesExt(reflect.TypeOf(uuid.UUID{}), 1, common.UuidExt{})
	enc := codec.NewEncoder(fo, &h)
	enc.Encode(pd)
}
