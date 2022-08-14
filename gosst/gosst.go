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
    ForkCalibration calibration
    ShockCalibration calibration
    WheelLeverageRatio [][2]float64
    CoeffsShockWheel []float64
    Time []float64
    FrontTravel []float64
    RearTravel []float64
}

type record struct {
    Micros uint32
    ForkAngle uint16
    ShockAngle uint16
}

type calibration struct {
    ArmLength float64
    MaxDistance float64
    MaxTravel float64
    StartAngle float64
}

func newCalibration(armLength, maxDistance, maxTravel float64) *calibration {
    a := math.Acos(maxDistance / 2.0 / armLength)
    return &calibration {
        ArmLength: armLength,
        MaxDistance: maxDistance,
        MaxTravel: maxTravel,
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

func angleToTravel(angle uint16, calibration calibration) float64 {
    a := math.Pi / 4096.0 * float64(angle)
    d := 2.0 * calibration.ArmLength * math.Cos(a + calibration.StartAngle)
    return calibration.MaxDistance - d
}

func main() {
    var opts struct {
        TelemetryFile string `short:"t" long:"telemetry" description:"Telemetry data file (.SST)" required:"true"`
        LeverageRatioFile string `short:"l" long:"leverageratio" description:"Leverage ratio file" required:"true"`
        CalibrationData string `short:"c" long:"calibration" description:"Calibration data" default:"120,218,180,88,138,65"`
        OutputFile string `short:"o" long:"output" description:"Output file"`
    }
    _, err := flags.Parse(&opts)
    if err != nil {
        return
    }

    var processedData processed
    processedData.Name = opts.TelemetryFile

    var farm, fmaxdist, fmaxtravel, sarm, smaxdist, smaxtravel float64
    _, err = fmt.Sscanf(opts.CalibrationData, "%f,%f,%f,%f,%f,%f", &farm, &fmaxdist, &fmaxtravel, &sarm, &smaxdist, &smaxtravel)
    if err != nil {
        log.Fatalln(err)
    }
    processedData.ForkCalibration = *newCalibration(farm, fmaxdist, fmaxtravel)
    processedData.ShockCalibration = *newCalibration(sarm, smaxdist, smaxtravel)

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

    fi, err := f.Stat()
    if err != nil {
        log.Fatalln(err)
    }
    records := make([]record, fi.Size() / 8)
    err = binary.Read(f, binary.LittleEndian, &records)
    if err != nil {
        log.Fatalln(err)
    }

    processedData.WheelLeverageRatio, processedData.CoeffsShockWheel = parseLeverageData(lrf)
    p, _ := polygo.NewRealPolynomial(processedData.CoeffsShockWheel)
    processedData.Time = make([]float64, len(records))
    processedData.FrontTravel = make([]float64, len(records))
    processedData.RearTravel = make([]float64, len(records))
    for index, value := range records {
        processedData.Time[index] = float64(index) * 0.0002
        processedData.FrontTravel[index] = angleToTravel(value.ForkAngle, processedData.ForkCalibration)
        processedData.RearTravel[index] = p.At(angleToTravel(value.ShockAngle, processedData.ShockCalibration))
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
    enc.Encode(processedData)
}
