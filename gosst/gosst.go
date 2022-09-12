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
	"sort"
	"strings"

	"github.com/SeanJxie/polygo"
	"github.com/jessevdk/go-flags"
	"github.com/openacid/slimarray/polyfit"
	"github.com/pconstantinou/savitzkygolay"
	"github.com/ugorji/go/codec"
	"gonum.org/v1/gonum/floats"
)

type digitized struct {
    Data []int
    Bins []float64
}

type frame struct {
    WheelLeverageRatio [][2]float64
    CoeffsShockWheel []float64
    MaxRearTravel float64
}

type calibration struct {
    ArmLength float64
    MaxDistance float64
    MaxStroke float64
    StartAngle float64
}

type suspension struct {
    Present bool
    Calibration calibration
    Travel []float64
    Velocity []float64
    DigitizedTravel digitized
    DigitizedVelocity digitized
}

type processed struct {
    Name string
    Version uint8
    SampleRate uint16
    Front suspension
    Rear suspension
    Frame frame
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
    if angle > 1024 { // XXX: Rotated backwards past the set 0 angle. Maybe we should report occurances like this.
        angle = 0
    }
    a := 2.0 * math.Pi / 4096.0 * float64(angle)
    d := 2.0 * calibration.ArmLength * math.Cos(a + calibration.StartAngle)
    return calibration.MaxDistance - d
}

func linspace(min, max float64, num int) []float64 {
    step := (max - min) / float64(num - 1)
    bins := make([]float64, num)
    for i := range bins {bins[i] = min + step * float64(i)}
    return bins
}

func digitize(data, bins []float64) []int {
    inds := make([]int, len(data))
    for k, v := range data {
        i := sort.SearchFloat64s(bins, v)
        // If current value is not exactly a bin boundary, we subtract 1 to make
        // the digitized slice indexed from 0 instead of 1. We do the same if a
        // value would exceed existing bins.
        if v >= bins[len(bins) - 1] || v != bins[i] {
            i -= 1
        }
        inds[k] = i
    }
    return inds
}

func digitizeVelocity(v []float64, d *digitized) {
    step := 50.0
    mn := (math.Floor(floats.Min(v) / step) - 0.5) * step  // Subtracting half bin ensures that 0 will be at the middle of one bin
    mx := (math.Floor(floats.Max(v) / step) + 1.5) * step  // Adding 1.5 bins ensures that all values will fit in bins, and that
                                                           // the last bin fits the step boundary.
    bins := linspace(mn, mx, int((mx - mn) / step) + 1)
    d.Bins = bins
    d.Data = digitize(v, bins)
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

    var pd processed
    pd.Name = opts.TelemetryFile

    var farm, fmaxdist, fmaxstroke, sarm, smaxdist, smaxstroke float64
    _, err = fmt.Sscanf(opts.CalibrationData, "%f,%f,%f,%f,%f,%f", &farm, &fmaxdist, &fmaxstroke, &sarm, &smaxdist, &smaxstroke)
    if err != nil {
        log.Fatalln(err)
    }
    pd.Front.Calibration = *newCalibration(farm, fmaxdist, fmaxstroke, opts.CalibrationInModule)
    pd.Rear.Calibration = *newCalibration(sarm, smaxdist, smaxstroke, opts.CalibrationInModule)

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
        pd.Version = fileHeader.Version
        pd.SampleRate = fileHeader.SampleRate
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
    // TODO: Using index 1 here to be compatible with SST files generated with
    // an earlier firmware version that contained an off-by-one error. This
    // should no cause any trouble, but should eventually set back to 0.
    var hasFront = records[1].ForkAngle != 0xffff
    pd.Front.Present = hasFront
    var hasRear = records[1].ShockAngle != 0xffff
    pd.Rear.Present = hasRear

    var frame frame
    frame.WheelLeverageRatio, frame.CoeffsShockWheel = parseLeverageData(lrf)
    p, _ := polygo.NewRealPolynomial(frame.CoeffsShockWheel)
    frame.MaxRearTravel = p.At(pd.Rear.Calibration.MaxStroke)

    if hasFront {
        pd.Front.Travel = make([]float64, len(records))
    }
    if hasRear {
        pd.Rear.Travel = make([]float64, len(records))
    }
    for index, value := range records {
        if hasFront {
            // Front travel might under/overshoot because of erronous data
            // acqusition. Errors might occur mid-ride (e.g. broken electrical
            // connection due to vibration), so we don't error out, just cap
            // travel. Errors like these will be obvious on the graphs, and
            // the affected regions can be filtered by hand.
            x := angleToStroke(value.ForkAngle, pd.Front.Calibration)
            x = math.Max(0, x)
            x = math.Min(x, pd.Front.Calibration.MaxStroke)
            pd.Front.Travel[index] = x
        }
        if hasRear {
            // Rear travel might also overshoot the max because of
            //  a) inaccurately measured leverage ratio
            //  b) inaccuracies introduced by polynomial fitting
            // So we just cap it at calculated maximum.
            x := p.At(angleToStroke(value.ShockAngle, pd.Rear.Calibration))
            x = math.Max(0, x)
            x = math.Min(x, frame.MaxRearTravel)
            pd.Rear.Travel[index] = x
        }
    }
    pd.Frame = frame

    if hasFront {
        tb := linspace(0, pd.Front.Calibration.MaxStroke, 21)
        pd.Front.DigitizedTravel.Bins = tb
        pd.Front.DigitizedTravel.Data = digitize(pd.Front.Travel, tb)
    }
    if hasRear {
        tb := linspace(0, pd.Frame.MaxRearTravel, 21)
        pd.Rear.DigitizedTravel.Bins = tb
        pd.Rear.DigitizedTravel.Data = digitize(pd.Rear.Travel, tb)
    }

    time := make([]float64, len(records))
    for i := range time {time[i] = 1.0 / float64(pd.SampleRate) * float64(i)}
    filter, _ := savitzkygolay.NewFilter(51, 1, 3)
    if hasFront {
        vf, _ := filter.Process(pd.Front.Travel, time)
        pd.Front.Velocity = vf
        digitizeVelocity(vf, &pd.Front.DigitizedVelocity)
    }
    if hasRear {
        vr, _ := filter.Process(pd.Rear.Travel, time)
        pd.Rear.Velocity = vr
        digitizeVelocity(vr, &pd.Rear.DigitizedVelocity)
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
