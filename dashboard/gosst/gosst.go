package main

import (
    "bufio"
    "encoding/binary"
    "fmt"
    "io"
    "log"
    "math"
    "os"
    "path"
    "strings"

    "github.com/jessevdk/go-flags"
    "github.com/openacid/slimarray/polyfit"
    "github.com/SeanJxie/polygo"
    "github.com/ugorji/go/codec"
    "gonum.org/v1/gonum/floats"
)

type processed struct {
    Name string
    Version uint8
    SampleRate uint16
    ForkCalibration calibration
    ShockCalibration calibration
    FrontTravel []float64
    RearTravel []float64
    LeverageData leverage
}

type leverage struct {
    WheelLeverageRatio [][2]float64
    CoeffsShockWheel []float64
    MaxRearTravel float64
}

type header struct {
    Magic [3]byte
    Version uint8
    SampleRate uint16
}

type record struct {
    ForkAngle uint16
    ShockAngle uint16
}

type calibration struct {
    ArmLength float64
    MaxDistance float64
    MaxStroke float64
    StartAngle float64
}

func newCalibration(armLength, maxDistance, maxStroke float64, useLegoModule bool) *calibration {
    if useLegoModule {
        // 1M = 5/16 inch = 7.9375 mm
        armLength = armLength * 7.9375
        maxDistance = maxDistance * 7.9375
    }
    a := math.Acos(maxDistance / 2.0 / armLength)
    return &calibration {
        ArmLength: armLength,
        MaxDistance: maxDistance,
        MaxStroke: maxStroke,
        StartAngle: a,
    }
}

func parseLeverageData(data io.Reader) ([][2]float64, []float64) {
    var wtlr [][2]float64
    var ilr []float64
    var wt []float64
    scanner := bufio.NewScanner(data)
    for scanner.Scan() {
        var w, l float64
        _, err := fmt.Sscanf(scanner.Text(), "%f,%f", &w, &l)
        if err == nil {
            ilr = append(ilr, 1.0/l)
            wtlr = append(wtlr, [2]float64{w, l})
            wt = append(wt, w)
        }
    }

    s := make([]float64, len(ilr))
    floats.CumSum(s, ilr)
    s = append([]float64{0.0}, s[:len(s)-1]...)
    
    f := polyfit.NewFit(s, wt, 3)
    coeffsShockWheel := f.Solve()

    return wtlr, coeffsShockWheel
}

func angleToStroke(angle uint16, calibration calibration) float64 {
    a := math.Pi / 4096.0 * float64(angle)
    d := 2.0 * calibration.ArmLength * math.Cos(a + calibration.StartAngle)
    return calibration.MaxDistance - d
}

func main() {
    var opts struct {
        TelemetryFile string `short:"t" long:"telemetry" description:"Telemetry data file (.SST)" required:"true"`
        LeverageRatioFile string `short:"l" long:"leverageratio" description:"Leverage ratio file" required:"true"`
        CalibrationData string `short:"c" long:"calibration" description:"Calibration data (arm, max. distance, max stroke for front and rear)" default:"120,218,180,88,138,65"`
        CalibrationInModule bool `short:"m" long:"lego" description:"If present, arm and max. distance are considered to be in LEGO Module"`
        OutputFile string `short:"o" long:"output" description:"Output file"`
    }
    _, err := flags.Parse(&opts)
    if err != nil {
        return
    }

    var processedData processed
    processedData.Name = opts.TelemetryFile

    var farm, fmaxdist, fmaxstroke, sarm, smaxdist, smaxstroke float64
    _, err = fmt.Sscanf(opts.CalibrationData, "%f,%f,%f,%f,%f,%f", &farm, &fmaxdist, &fmaxstroke, &sarm, &smaxdist, &smaxstroke)
    if err != nil {
        log.Fatalln(err)
    }
    processedData.ForkCalibration = *newCalibration(farm, fmaxdist, fmaxstroke, opts.CalibrationInModule)
    processedData.ShockCalibration = *newCalibration(sarm, smaxdist, smaxstroke, opts.CalibrationInModule)

    lrf, err := os.Open(opts.LeverageRatioFile)
    if err != nil {
        log.Fatalln(err)
    }
    defer lrf.Close()

    f, err := os.Open(opts.TelemetryFile)
    if err != nil {
        log.Fatalln(err)
    }
    defer f.Close()

    headers := make([]header, 1)
    err = binary.Read(f, binary.LittleEndian, &headers)
    if err != nil {
        log.Fatalln(err)
    }
    fileHeader := headers[0]
    if string(fileHeader.Magic[:]) == "SST" {
        processedData.Version = fileHeader.Version
        processedData.SampleRate = fileHeader.SampleRate
    } else {
        log.Fatalln("Input file is old (versionless), please use gosst-old!")
    }

    fi, err := f.Stat()
    if err != nil {
        log.Fatalln(err)
    }
    records := make([]record, (fi.Size() - 6 /* sizeof(heaeder) */) / 4 /* sizeof(record) */)
    err = binary.Read(f, binary.LittleEndian, &records)
    if err != nil {
        log.Fatalln(err)
    }

    var leverageData leverage
    leverageData.WheelLeverageRatio, leverageData.CoeffsShockWheel = parseLeverageData(lrf)
    p, _ := polygo.NewRealPolynomial(leverageData.CoeffsShockWheel)
    processedData.FrontTravel = make([]float64, len(records))
    processedData.RearTravel = make([]float64, len(records))
    for index, value := range records {
        processedData.FrontTravel[index] = angleToStroke(value.ForkAngle, processedData.ForkCalibration)
        processedData.RearTravel[index] = p.At(angleToStroke(value.ShockAngle, processedData.ShockCalibration))
    }
    leverageData.MaxRearTravel = p.At(processedData.ShockCalibration.MaxStroke)
    processedData.LeverageData = leverageData

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
    enc.Encode(processedData)
}
