package main

import (
	"log"
	"os"
	"path"
	"strings"

	"encoding/json"
	"github.com/jessevdk/go-flags"
	"github.com/ugorji/go/codec"

	psst "gosst/internal/psst"
)

type calibrations struct {
	FrontCalibration psst.Calibration       `json:"fcal"`
	FrontMethod      psst.CalibrationMethod `json:"fmethod"`
	RearCalibration  psst.Calibration       `json:"rcal"`
	RearMethod       psst.CalibrationMethod `json:"rmethod"`
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

	var calibrations calibrations
	c, err := os.ReadFile(opts.Calibration)
	if err != nil {
		log.Fatalln(err)
	}
	if err = json.Unmarshal(c, &calibrations); err != nil {
		log.Fatalln(err)
	}
	calibrations.FrontCalibration.Method = calibrations.FrontMethod
	if err = calibrations.FrontCalibration.Prepare(); err != nil {
		log.Fatalln(err)
	}
	calibrations.RearCalibration.Method = calibrations.RearMethod
	if err = calibrations.RearCalibration.Prepare(); err != nil {
		log.Fatalln(err)
	}

	tb, err := os.ReadFile(opts.TelemetryFile)
	if err != nil {
		log.Fatalln(err)
	}

	pd := psst.ProcessRecording(tb, opts.TelemetryFile, linkage, *&calibrations.FrontCalibration, calibrations.RearCalibration)

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