package psst

import (
	"bufio"
	"fmt"
	"math"
	"strings"

	"github.com/SeanJxie/polygo"
	"github.com/google/uuid"
	"github.com/openacid/slimarray/polyfit"
	"github.com/pconstantinou/savitzkygolay"
	"golang.org/x/exp/constraints"
)

const (
	VELOCITY_ZERO_THRESHOLD             = 0.02  // (mm/s) maximum velocity to be considered as zero
	IDLING_DURATION_THRESHOLD           = 0.10  // (s) minimum duration to consider stroke an idle period
	AIRTIME_TRAVEL_THRESHOLD            = 3     // (mm) maximum travel to consider stroke an airtime
	AIRTIME_DURATION_THRESHOLD          = 0.20  // (s) minimum duration to consider stroke an airtime
	AIRTIME_VELOCITY_THRESHOLD          = 500   // (mm/s) minimum velocity after stroke to consider it an airtime
	AIRTIME_OVERLAP_THRESHOLD           = 0.5   // f&r airtime candidates must overlap at least this amount to be an airtime
	AIRTIME_TRAVEL_MEAN_THRESHOLD_RATIO = 0.04  // stroke f&r mean travel must be below max*this to be an airtime
	STROKE_LENGTH_THRESHOLD             = 5     // (mm) minimum length to consider stroke a compression/rebound
	TRAVEL_HIST_BINS                    = 20    // number of travel histogram bins
	VELOCITY_HIST_TRAVEL_BINS           = 10    // number of travel histogram bins for velocity histogram
	VELOCITY_HIST_STEP                  = 100.0 // (mm/s) step between velocity histogram bins
	VELOCITY_HIST_STEP_FINE             = 15.0  // (mm/s) step between fine-grained velocity histogram bins
	BOTTOMOUT_THRESHOLD                 = 3     // (mm) bottomouts are regions where travel > max_travel - this value
)

type LinkageRecord struct {
	ShockTravel   float64
	WheelTravel   float64
	LeverageRatio float64
}

type Linkage struct {
	Id               uuid.UUID    `codec:"-" db:"id"           json:"id"`
	Name             string       `codec:"," db:"name"         json:"name"         binding:"required"`
	HeadAngle        float64      `codec:"," db:"head_angle"   json:"head_angle"   binding:"required"`
	RawData          string       `codec:"-" db:"raw_lr_data"  json:"data"         binding:"required"`
	MaxFrontStroke   float64      `codec:"," db:"front_stroke" json:"front_stroke" binding:"required"`
	MaxRearStroke    float64      `codec:"," db:"rear_stroke"  json:"rear_stroke"  binding:"required"`
	MaxFrontTravel   float64      `codec:","                   json:"-"`
	MaxRearTravel    float64      `codec:","                   json:"-"`
	LeverageRatio    [][2]float64 `codec:","                   json:"-"`
	ShockWheelCoeffs []float64    `codec:","                   json:"-"`
	polynomial       *polygo.RealPolynomial
}

type suspension struct {
	Present          bool
	Calibration      Calibration
	Travel           []float64
	Velocity         []float64
	Strokes          strokes
	TravelBins       []float64
	VelocityBins     []float64
	FineVelocityBins []float64
}

type Number interface {
	constraints.Float | constraints.Integer
}

type Meta struct {
	Name       string
	Version    uint8
	SampleRate uint16
	Timestamp  int64
}

type SetupData struct {
	Linkage          *Linkage
	FrontCalibration *Calibration
	RearCalibration  *Calibration
}

type Processed struct {
	Meta
	Front    suspension
	Rear     suspension
	Linkage  Linkage
	Airtimes []*airtime
}

func (this *Linkage) ProcessRawData() error {
	var records []LinkageRecord
	scanner := bufio.NewScanner(strings.NewReader(this.RawData))
	s := 0.0
	for scanner.Scan() {
		var w, l float64
		_, err := fmt.Sscanf(scanner.Text(), "%f,%f", &w, &l)
		if err == nil {
			records = append(records, LinkageRecord{
				ShockTravel:   s,
				WheelTravel:   w,
				LeverageRatio: l,
			})
			s += 1.0 / l
		}
	}

	this.Process(records)
	return nil
}

func (this *Linkage) Process(records []LinkageRecord) {
	var st []float64
	var wt []float64
	var wtlr [][2]float64

	for _, record := range records {
		st = append(st, record.ShockTravel)
		wt = append(wt, record.WheelTravel)
		wtlr = append(wtlr, [2]float64{record.WheelTravel, record.LeverageRatio})
	}

	f := polyfit.NewFit(st, wt, 3)

	this.LeverageRatio = wtlr
	this.ShockWheelCoeffs = f.Solve()

	this.polynomial, _ = polygo.NewRealPolynomial(this.ShockWheelCoeffs)
	this.MaxRearTravel = this.polynomial.At(this.MaxRearStroke)
	this.MaxFrontTravel = math.Sin(this.HeadAngle*math.Pi/180.0) * this.MaxFrontStroke
}

func linspace(min, max float64, num int) []float64 {
	step := (max - min) / float64(num-1)
	bins := make([]float64, num)
	for i := range bins {
		bins[i] = min + step*float64(i)
	}
	return bins
}

type MissingRecordsError struct{}

func (e *MissingRecordsError) Error() string {
	return "Front and rear record arrays are empty"
}

type RecordCountMismatchError struct{}

func (e *RecordCountMismatchError) Error() string {
	return "Front and rear record counts are not equal"
}

func ProcessRecording[T Number](front, rear []T, meta Meta, setup *SetupData) (*Processed, error) {
	var pd Processed
	pd.Meta = meta
	pd.Front.Calibration = *setup.FrontCalibration
	pd.Rear.Calibration = *setup.RearCalibration
	pd.Linkage = *setup.Linkage

	fc := len(front)
	rc := len(rear)
	pd.Front.Present = fc != 0
	pd.Rear.Present = rc != 0
	if !(pd.Front.Present || pd.Rear.Present) {
		return nil, &MissingRecordsError{}
	} else if (pd.Front.Present && pd.Rear.Present) && (fc != rc) {
		return nil, &RecordCountMismatchError{}
	}
	record_count := max(fc, rc)

	t := make([]float64, record_count)
	for i := range t {
		t[i] = 1.0 / float64(pd.SampleRate) * float64(i)
	}
	filter, _ := savitzkygolay.NewFilter(51, 1, 3)

	if pd.Front.Present {
		pd.Front.Travel = make([]float64, fc)
		front_coeff := math.Sin(pd.Linkage.HeadAngle * math.Pi / 180.0)

		for idx, value := range front {
			// Front travel might under/overshoot because of erronous data
			// acqusition. Errors might occur mid-ride (e.g. broken electrical
			// connection due to vibration), so we don't error out, just cap
			// travel. Errors like these will be obvious on the graphs, and
			// the affected regions can be filtered by hand.
			out, _ := pd.Front.Calibration.Evaluate(float64(value))
			x := out * front_coeff
			x = math.Max(0, x)
			x = math.Min(x, pd.Linkage.MaxFrontTravel)
			pd.Front.Travel[idx] = x
		}

		tbins := linspace(0, pd.Linkage.MaxFrontTravel, TRAVEL_HIST_BINS+1)
		dt := digitize(pd.Front.Travel, tbins)
		pd.Front.TravelBins = tbins

		v, _ := filter.Process(pd.Front.Travel, t)
		pd.Front.Velocity = v
		vbins, dv := digitizeVelocity(v, VELOCITY_HIST_STEP)
		pd.Front.VelocityBins = vbins
		vbinsFine, dvFine := digitizeVelocity(v, VELOCITY_HIST_STEP_FINE)
		pd.Front.FineVelocityBins = vbinsFine

		strokes := filterStrokes(v, pd.Front.Travel, pd.Linkage.MaxFrontTravel, pd.SampleRate)
		pd.Front.Strokes.categorize(strokes, pd.Front.Travel, pd.Linkage.MaxFrontTravel)
		if len(pd.Front.Strokes.Compressions) == 0 && len(pd.Front.Strokes.Rebounds) == 0 {
			pd.Front.Present = false
		} else {
			pd.Front.Strokes.digitize(dt, dv, dvFine)
		}
	}
	if pd.Rear.Present {
		pd.Rear.Travel = make([]float64, rc)
		for idx, value := range rear {
			// Rear travel might also overshoot the max because of
			//  a) inaccurately measured leverage ratio
			//  b) inaccuracies introduced by polynomial fitting
			// So we just cap it at calculated maximum.
			out, _ := pd.Rear.Calibration.Evaluate(float64(value))
			x := pd.Linkage.polynomial.At(out)
			x = math.Max(0, x)
			x = math.Min(x, pd.Linkage.MaxRearTravel)
			pd.Rear.Travel[idx] = x
		}

		tbins := linspace(0, pd.Linkage.MaxRearTravel, TRAVEL_HIST_BINS+1)
		dt := digitize(pd.Rear.Travel, tbins)
		pd.Rear.TravelBins = tbins

		v, _ := filter.Process(pd.Rear.Travel, t)
		pd.Rear.Velocity = v
		vbins, dv := digitizeVelocity(v, VELOCITY_HIST_STEP)
		pd.Rear.VelocityBins = vbins
		vbinsFine, dvFine := digitizeVelocity(v, VELOCITY_HIST_STEP_FINE)
		pd.Rear.FineVelocityBins = vbinsFine

		strokes := filterStrokes(v, pd.Rear.Travel, pd.Linkage.MaxRearTravel, pd.SampleRate)
		pd.Rear.Strokes.categorize(strokes, pd.Rear.Travel, pd.Linkage.MaxRearTravel)
		if len(pd.Rear.Strokes.Compressions) == 0 && len(pd.Rear.Strokes.Rebounds) == 0 {
			pd.Rear.Present = false
		} else {
			pd.Rear.Strokes.digitize(dt, dv, dvFine)
		}
	}

	pd.airtimes()

	return &pd, nil
}
