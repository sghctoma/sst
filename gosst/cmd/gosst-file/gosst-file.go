package main

import (
	"fmt"
	"log"
	"os"
	"path"
	"strings"

	"github.com/jessevdk/go-flags"
	"github.com/ugorji/go/codec"

	psst "gosst/internal/psst"
)

func main() {
	var opts struct {
		TelemetryFile       string  `short:"t" long:"telemetry" description:"Telemetry data file (.SST)" required:"true"`
		LeverageRatioFile   string  `short:"l" long:"leverageratio" description:"Leverage ratio file" required:"true"`
		HeadAngle           float64 `short:"a" long:"headangle" description:"Head angle" required:"true"`
		CalibrationData     string  `short:"c" long:"calibration" description:"Calibration data (arm, max. distance, max stroke for front and rear)" required:"true"`
		CalibrationInModule bool    `short:"m" long:"lego" description:"If present, arm and max. distance are considered to be in LEGO Module"`
		OutputFile          string  `short:"o" long:"output" description:"Output file"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	var linkage psst.Linkage
	linkage.HeadAngle = opts.HeadAngle
	lb, err := os.ReadFile(opts.LeverageRatioFile)
	if err != nil {
		log.Fatalln(err)
	}
	linkage.RawData = string(lb)
	if linkage.Process() != nil {
		log.Fatalln(err)
	}

	var farm, fmaxdist, fmaxstroke, rarm, rmaxdist, rmaxstroke float64
	_, err = fmt.Sscanf(opts.CalibrationData, "%f,%f,%f,%f,%f,%f", &farm, &fmaxdist, &fmaxstroke, &rarm, &rmaxdist, &rmaxstroke)
	if err != nil {
		log.Fatalln(err)
	}
	fcal := psst.NewCalibration(farm, fmaxdist, fmaxstroke, opts.CalibrationInModule)
	rcal := psst.NewCalibration(rarm, rmaxdist, rmaxstroke, opts.CalibrationInModule)

	tb, err := os.ReadFile(opts.TelemetryFile)
	if err != nil {
		log.Fatalln(err)
	}

	pd := psst.ProcessRecording(tb, opts.TelemetryFile, linkage, *fcal, *rcal)

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