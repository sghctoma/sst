package main

import (
	"log"
	"os"
	"path"
	"strings"

	"github.com/jessevdk/go-flags"
	"github.com/ugorji/go/codec"

	psst "gosst/internal/formats/psst"
	sst "gosst/internal/formats/sst"
)

type calibrations struct {
	FrontCalibration psst.Calibration `json:"front"`
	RearCalibration  psst.Calibration `json:"rear"`
}

func main() {
	var opts struct {
		TelemetryFile     string  `short:"t" long:"telemetry" description:"Telemetry data file (.SST)" required:"true"`
		LeverageRatioFile string  `short:"l" long:"leverageratio" description:"Leverage ratio file" required:"true"`
		HeadAngle         float64 `short:"a" long:"headangle" description:"Head angle" required:"true"`
		MaxFrontStroke    float64 `short:"f" long:"frontmax" description:"Maximum stroke (front)" required:"true"`
		MaxRearStroke     float64 `short:"r" long:"rearmax" description:"Maximum stroke (rear)" required:"true"`
		Calibration       string  `short:"c" long:"calibration" description:"Calibration data file (JSON)" required:"true"`
		OutputFile        string  `short:"o" long:"output" description:"Output file"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	var linkage psst.Linkage
	linkage.HeadAngle = opts.HeadAngle
	linkage.MaxFrontStroke = opts.MaxFrontStroke
	linkage.MaxRearStroke = opts.MaxRearStroke
	lb, err := os.ReadFile(opts.LeverageRatioFile)
	if err != nil {
		log.Fatalln(err)
	}
	linkage.RawData = string(lb)
	if linkage.Process() != nil {
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
	pd, err := psst.ProcessRecording(front, rear, meta, linkage, *fcal, *rcal)
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
	enc := codec.NewEncoder(fo, &h)
	enc.Encode(pd)
}