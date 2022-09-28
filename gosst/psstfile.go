package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"math"
	"mime/multipart"
	"path"
	"sort"
	"strings"

	"github.com/SeanJxie/polygo"
	"github.com/google/uuid"
	"github.com/openacid/slimarray/polyfit"
	"github.com/pconstantinou/savitzkygolay"
	"gonum.org/v1/gonum/floats"
)

type calibration struct {
    ArmLength   float64 `codec:"," json:"arm" binding:"required"`
    MaxDistance float64 `codec:"," json:"dist" binding:"required"` 
    MaxStroke   float64 `codec:"," json:"stroke" binding:"required"` 
    StartAngle  float64 `codec:"," json:"angle"`
}

type linkage struct {
    Name             string       `codec:"," json:"name" binding:"required"`
    LeverageRatio    [][2]float64 `codec:"," json:"leverage" binding:"required"`
    ShockWheelCoeffs []float64    `codec:"," json:"coeffs"`
    MaxRearTravel    float64      `codec:"," json:"max_travel"`
}

type digitized struct {
    Data []int
    Bins []float64
}

type suspension struct {
    Present bool
    Calibration calibration
    Travel []float64
    Velocity []float64
    DigitizedTravel digitized
    DigitizedVelocity digitized
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

type processed struct {
    Name       string
    Version    uint8
    SampleRate uint16
    Front      suspension
    Rear       suspension
    Linkage    linkage
}

func newLinkage(name string, data io.Reader) *linkage {
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

    return &linkage {
        Name: name,
        LeverageRatio: wtlr,
        ShockWheelCoeffs: f.Solve(),
        MaxRearTravel: wt[len(wt) - 1],
    }
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


func prorcessRecording(file *multipart.FileHeader, lnk linkage, fcal, rcal calibration) *processed {
    filename := path.Base(file.Filename)
    if filename == "" {
        filename = fmt.Sprintf("%s.PSST", uuid.UUID{}.String())
    } else {
        ext := path.Ext(filename)
        if ext == "" {
            filename = fmt.Sprintf("%s.PSST", filename)
        } else {
            n := strings.LastIndex(filename, ext)
            filename = fmt.Sprintf("%s.PSST", filename[:n])
        }
    }

    var pd processed
    pd.Name = filename
    pd.Front.Calibration = fcal
    pd.Rear.Calibration = rcal

    p, _ := polygo.NewRealPolynomial(lnk.ShockWheelCoeffs)
    lnk.MaxRearTravel = p.At(pd.Rear.Calibration.MaxStroke)
    pd.Linkage = lnk

    f, _ := file.Open()
    headers := make([]header, 1)
    err := binary.Read(f, binary.LittleEndian, &headers)
    if err != nil {
        return nil
    }
    fileHeader := headers[0]

    if string(fileHeader.Magic[:]) == "SST" {
        pd.Version = fileHeader.Version
        pd.SampleRate = fileHeader.SampleRate
    } else {
        return nil
    }

    records := make([]record, (file.Size - 6 /* sizeof(heaeder) */) / 4 /* sizeof(record) */)
    err = binary.Read(f, binary.LittleEndian, &records)
    if err != nil {
        return nil
    }
    // TODO: Using index 1 here to be compatible with SST files generated with
    // an earlier firmware version that contained an off-by-one error. This
    // should no cause any trouble, but should eventually set back to 0.
    var hasFront = records[1].ForkAngle != 0xffff
    pd.Front.Present = hasFront
    var hasRear = records[1].ShockAngle != 0xffff
    pd.Rear.Present = hasRear

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
            x = math.Min(x, lnk.MaxRearTravel)
            pd.Rear.Travel[index] = x
        }
    }

    if hasFront {
        tb := linspace(0, pd.Front.Calibration.MaxStroke, 21)
        pd.Front.DigitizedTravel.Bins = tb
        pd.Front.DigitizedTravel.Data = digitize(pd.Front.Travel, tb)
    }
    if hasRear {
        tb := linspace(0, pd.Linkage.MaxRearTravel, 21)
        pd.Rear.DigitizedTravel.Bins = tb
        pd.Rear.DigitizedTravel.Data = digitize(pd.Rear.Travel, tb)
    }

    t := make([]float64, len(records))
    for i := range t {t[i] = 1.0 / float64(pd.SampleRate) * float64(i)}
    filter, _ := savitzkygolay.NewFilter(51, 1, 3)
    if hasFront {
        vf, _ := filter.Process(pd.Front.Travel, t)
        pd.Front.Velocity = vf
        digitizeVelocity(vf, &pd.Front.DigitizedVelocity)
    }
    if hasRear {
        vr, _ := filter.Process(pd.Rear.Travel, t)
        pd.Rear.Velocity = vr
        digitizeVelocity(vr, &pd.Rear.DigitizedVelocity)
    }

    return &pd
}
