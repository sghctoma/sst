package psst

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"fmt"
	"math"
	"sort"
	"strings"

	"github.com/SeanJxie/polygo"
	"github.com/openacid/slimarray/polyfit"
	"github.com/pconstantinou/savitzkygolay"
	"gonum.org/v1/gonum/floats"
	"gonum.org/v1/gonum/stat"
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
)

type Calibration struct {
	Id          int     `codec:"-" db:"calibration_id" json:"id"`
	Name        string  `codec:"," db:"name"           json:"name"   binding:"required"`
	ArmLength   float64 `codec:"," db:"arm"            json:"arm"    binding:"required"`
	MaxDistance float64 `codec:"," db:"dist"           json:"dist"   binding:"required"`
	MaxStroke   float64 `codec:"," db:"stroke"         json:"stroke" binding:"required"`
	StartAngle  float64 `codec:"," db:"angle"          json:"angle"`
}

type Linkage struct {
	Id               int          `codec:"-" db:"linkage_id"  json:"id"`
	Name             string       `codec:"," db:"name"        json:"name"       binding:"required"`
	RawData          string       `codec:"-" db:"raw_lr_data" json:"data"       binding:"required"`
	LeverageRatio    [][2]float64 `codec:","                  json:"leverage"`
	ShockWheelCoeffs []float64    `codec:","                  json:"coeffs"`
	MaxRearTravel    float64      `codec:","                  json:"max_travel"`
}

type suspension struct {
	Present     bool
	Calibration Calibration
	Travel      []float64
	Velocity    []float64
	Strokes     strokes
}

type header struct {
	Magic      [3]byte
	Version    uint8
	SampleRate uint16
	Padding    uint16
	Timestamp  int64
}

type record struct {
	ForkAngle  uint16
	ShockAngle uint16
}

type balance struct {
	Position float64
	Velocity float64
}

type stroke struct {
	Start        int
	End          int
	Balance      balance
	TravelHist   [TRAVEL_HIST_BINS]float32
	VelocityHist [][VELOCITY_HIST_TRAVEL_BINS]float32
	length       float64
	duration     float64
	airCandidate bool
	posMin       float64
	posMax       float64
	velMin       float64
	velMax       float64
}

type strokes struct {
	Compressions []*stroke
	Rebounds     []*stroke
	idlings      []*stroke
	totalCount   int
}

type airtime struct {
	Start float64
	End   float64
}

type processed struct {
	Name       string
	Version    uint8
	SampleRate uint16
	Timestamp  int64
	Front      suspension
	Rear       suspension
	Linkage    Linkage
	Airtimes   []*airtime
}

func NewCalibration(armLength, maxDistance, maxStroke float64, useLegoModule bool) *Calibration {
	if useLegoModule {
		// 1M = 5/16 inch = 7.9375 mm
		armLength = armLength * 7.9375
		maxDistance = maxDistance * 7.9375
	}
	a := math.Acos(maxDistance / 2.0 / armLength)
	return &Calibration{
		Name:        "",
		ArmLength:   armLength,
		MaxDistance: maxDistance,
		MaxStroke:   maxStroke,
		StartAngle:  a,
	}
}

func (this *Linkage) Process() error {
	var wtlr [][2]float64
	var ilr []float64
	var wt []float64
	scanner := bufio.NewScanner(strings.NewReader(this.RawData))
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

	this.LeverageRatio = wtlr
	this.ShockWheelCoeffs = f.Solve()
	this.MaxRearTravel = wt[len(wt)-1]

	return nil
}

func angleToStroke(angle uint16, calibration Calibration) float64 {
	if angle > 1024 { // XXX: Rotated backwards past the set 0 angle. Maybe we should report occurances like this.
		angle = 0
	}
	a := 2.0 * math.Pi / 4096.0 * float64(angle)
	d := 2.0 * calibration.ArmLength * math.Cos(a+calibration.StartAngle)
	return calibration.MaxDistance - d
}

func linspace(min, max float64, num int) []float64 {
	step := (max - min) / float64(num-1)
	bins := make([]float64, num)
	for i := range bins {
		bins[i] = min + step*float64(i)
	}
	return bins
}

func digitize(data, bins []float64) []int {
	inds := make([]int, len(data))
	for k, v := range data {
		i := sort.SearchFloat64s(bins, v)
		// If current value is not exactly a bin boundary, we subtract 1 to make
		// the digitized slice indexed from 0 instead of 1. We do the same if a
		// value would exceed existing bins.
		if v >= bins[len(bins)-1] || v != bins[i] {
			i -= 1
		}
		inds[k] = i
	}
	return inds
}

func digitizeVelocity(v []float64) (bins []float64, data []int) {
	step := VELOCITY_HIST_STEP
	mn := (math.Floor(floats.Min(v)/step) - 0.5) * step // Subtracting half bin ensures that 0 will be at the middle of one bin
	mx := (math.Floor(floats.Max(v)/step) + 1.5) * step // Adding 1.5 bins ensures that all values will fit in bins, and that
	// the last bin fits the step boundary.
	bins = linspace(mn, mx, int((mx-mn)/step)+1)
	data = digitize(v, bins)
	return bins, data
}

func (this *stroke) calculateHistograms(dt, dv []int, vbl int, totalCount int) {
	this.VelocityHist = make([][10]float32, vbl)
	step := 1.0 / float32(totalCount) * 100.0
	for i := this.Start; i <= this.End; i++ {
		tbin := dt[i]
		vbin := dv[i]
		tbinv := dt[i] / (TRAVEL_HIST_BINS / VELOCITY_HIST_TRAVEL_BINS)
		this.TravelHist[tbin] += step
		this.VelocityHist[vbin][tbinv] += step
	}
}

func (this *strokes) categorize(strokes []*stroke, travel []float64, maxTravel float64) {
	for i, stroke := range strokes {
		if math.Abs(stroke.length) < STROKE_LENGTH_THRESHOLD &&
			stroke.duration >= IDLING_DURATION_THRESHOLD {

			// If suitable, tag this idling stroke as possible airtime.
			// Whether or not it really is one, will be decided with
			// further heuristics based on both front and read
			// candidates.
			if i > 0 && i < len(strokes)-1 &&
				stroke.posMax <= STROKE_LENGTH_THRESHOLD &&
				stroke.duration >= AIRTIME_DURATION_THRESHOLD &&
				strokes[i+1].velMax >= AIRTIME_VELOCITY_THRESHOLD {

				stroke.airCandidate = true
			}
			this.idlings = append(this.idlings, stroke)
		} else if stroke.length >= STROKE_LENGTH_THRESHOLD {
			stroke.Balance = balance{
				Position: stroke.posMax / maxTravel * 100.0,
				Velocity: stroke.velMax,
			}
			this.totalCount += (stroke.End - stroke.Start + 1)
			this.Compressions = append(this.Compressions, stroke)
		} else if stroke.length <= -STROKE_LENGTH_THRESHOLD {
			stroke.Balance = balance{
				Position: stroke.posMin / maxTravel * 100.0,
				Velocity: stroke.velMin,
			}
			this.totalCount += (stroke.End - stroke.Start + 1)
			this.Rebounds = append(this.Rebounds, stroke)
		}
	}
}

func (this *strokes) histograms(dt, dv []int, vbl int) {
	for _, s := range this.Compressions {
		s.calculateHistograms(dt, dv, vbl, this.totalCount)
	}
	for _, s := range this.Rebounds {
		s.calculateHistograms(dt, dv, vbl, this.totalCount)
	}
}

func sign(v float64) int8 {
	if math.Abs(v) <= VELOCITY_ZERO_THRESHOLD {
		return 0
	} else if math.Signbit(v) {
		return -1
	} else {
		return 1
	}
}

func filterStrokes(velocity, travel []float64, rate uint16) (strokes []*stroke) {
	var start_index int
	var start_sign int8
	for i := 0; i < len(velocity)-1; i++ {
		// Loop until velocity changes sign
		start_index = i
		start_sign = sign(velocity[i])
		for ; i < len(velocity)-1 && sign(velocity[i+1]) == start_sign; i++ {
		}

		// We are at the end of the data stream
		if i >= len(velocity) {
			i = len(velocity) - 1
		}

		// Topout periods often oscillate a bit, so they are split to multiple
		// strokes. We fix this by concatenating consecutive strokes if their
		// mean position is close to zero.
		d := float64(i-start_index+1) / float64(rate)
		pm := floats.Max(travel[start_index : i+1])
		if pm < STROKE_LENGTH_THRESHOLD &&
			len(strokes) > 0 &&
			strokes[len(strokes)-1].posMax < STROKE_LENGTH_THRESHOLD {

			strokes[len(strokes)-1].End = i
			strokes[len(strokes)-1].duration += d
		} else {
			s := &stroke{
				Start:    start_index,
				End:      i,
				length:   travel[i] - travel[start_index],
				duration: d,
				posMin:   floats.Min(travel[start_index : i+1]),
				posMax:   floats.Max(travel[start_index : i+1]),
				velMin:   floats.Min(velocity[start_index : i+1]),
				velMax:   floats.Max(velocity[start_index : i+1]),
			}
			strokes = append(strokes, s)
		}
	}

	return strokes
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func (this *stroke) overlaps(other *stroke) bool {
	l := max(this.End-this.Start, other.End-other.Start)
	s := max(this.Start, other.Start)
	e := min(this.End, other.End)
	return float32(e-s) >= AIRTIME_OVERLAP_THRESHOLD*float32(l)
}

func (this *processed) airtimes() {
	if this.Front.Present && this.Rear.Present {
		for _, f := range this.Front.Strokes.idlings {
			if f.airCandidate {
				for _, r := range this.Rear.Strokes.idlings {
					if r.airCandidate && f.overlaps(r) {
						f.airCandidate = false
						r.airCandidate = false

						at := &airtime{
							Start: float64(min(f.Start, r.Start)) / float64(this.SampleRate),
							End:   float64(min(f.End, r.End)) / float64(this.SampleRate),
						}
						this.Airtimes = append(this.Airtimes, at)
						break
					}
				}
			}
		}
		maxMean := (this.Front.Calibration.MaxStroke + this.Linkage.MaxRearTravel) / 2.0
		for _, f := range this.Front.Strokes.idlings {
			if f.airCandidate {
				fmean := stat.Mean(this.Front.Travel[f.Start:f.End+1], nil)
				rmean := stat.Mean(this.Rear.Travel[f.Start:f.End+1], nil)
				if (fmean+rmean)/2 <= maxMean*AIRTIME_TRAVEL_MEAN_THRESHOLD_RATIO {
					at := &airtime{
						Start: float64(f.Start) / float64(this.SampleRate),
						End:   float64(f.End) / float64(this.SampleRate),
					}
					this.Airtimes = append(this.Airtimes, at)
				}
			}
		}
		for _, r := range this.Rear.Strokes.idlings {
			if r.airCandidate {
				fmean := stat.Mean(this.Front.Travel[r.Start:r.End+1], nil)
				rmean := stat.Mean(this.Rear.Travel[r.Start:r.End+1], nil)
				if (fmean+rmean)/2 <= maxMean*AIRTIME_TRAVEL_MEAN_THRESHOLD_RATIO {
					at := &airtime{
						Start: float64(r.Start) / float64(this.SampleRate),
						End:   float64(r.End) / float64(this.SampleRate),
					}
					this.Airtimes = append(this.Airtimes, at)
				}
			}
		}
	} else if this.Front.Present {
		for _, f := range this.Front.Strokes.idlings {
			if f.airCandidate {
				at := &airtime{
					Start: float64(f.Start) / float64(this.SampleRate),
					End:   float64(f.End) / float64(this.SampleRate),
				}
				this.Airtimes = append(this.Airtimes, at)
			}
		}
	} else if this.Rear.Present {
		for _, r := range this.Rear.Strokes.idlings {
			if r.airCandidate {
				at := &airtime{
					Start: float64(r.Start) / float64(this.SampleRate),
					End:   float64(r.End) / float64(this.SampleRate),
				}
				this.Airtimes = append(this.Airtimes, at)
			}
		}
	}
}

func ProcessRecording(sst []byte, name string, lnk Linkage, fcal, rcal Calibration) *processed {
	var pd processed
	pd.Name = name
	pd.Front.Calibration = fcal
	pd.Rear.Calibration = rcal

	p, _ := polygo.NewRealPolynomial(lnk.ShockWheelCoeffs)
	lnk.MaxRearTravel = p.At(pd.Rear.Calibration.MaxStroke)
	pd.Linkage = lnk

	f := bytes.NewReader(sst)
	headers := make([]header, 1)
	err := binary.Read(f, binary.LittleEndian, &headers)
	if err != nil {
		return nil
	}
	fileHeader := headers[0]

	if string(fileHeader.Magic[:]) == "SST" {
		pd.Version = fileHeader.Version
		pd.SampleRate = fileHeader.SampleRate
		pd.Timestamp = fileHeader.Timestamp
	} else {
		return nil
	}

	records := make([]record, (len(sst)-16 /* sizeof(header) */)/4 /* sizeof(record) */)
	err = binary.Read(f, binary.LittleEndian, &records)
	if err != nil {
		return nil
	}
	var hasFront = records[0].ForkAngle != 0xffff
	pd.Front.Present = hasFront
	var hasRear = records[0].ShockAngle != 0xffff
	pd.Rear.Present = hasRear

	// Rudimentary attempt to fix datasets where the sensor jumps to an unreasonably
	// large number after a few tenth of seconds, but measures everything correctly
	// from that baseline.
	var frontError, rearError uint16
	var frontBaseline, rearBaseline uint16
	frontError = 0
	frontBaseline = records[0].ForkAngle
	for _, r := range records[1:] {
		if r.ForkAngle > frontBaseline {
			if r.ForkAngle > 0x0050 {
				frontError = r.ForkAngle
			}
			break
		}
	}
	rearError = 0
	rearBaseline = records[0].ShockAngle
	for _, r := range records[1:] {
		if r.ShockAngle > rearBaseline {
			if r.ShockAngle > 0x0050 {
				rearError = r.ShockAngle
			}
			break
		}
	}

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
			x := angleToStroke(value.ForkAngle-frontError, pd.Front.Calibration)
			x = math.Max(0, x)
			x = math.Min(x, pd.Front.Calibration.MaxStroke)
			pd.Front.Travel[index] = x
		}
		if hasRear {
			// Rear travel might also overshoot the max because of
			//  a) inaccurately measured leverage ratio
			//  b) inaccuracies introduced by polynomial fitting
			// So we just cap it at calculated maximum.
			x := p.At(angleToStroke(value.ShockAngle-rearError, pd.Rear.Calibration))
			x = math.Max(0, x)
			x = math.Min(x, lnk.MaxRearTravel)
			pd.Rear.Travel[index] = x
		}
	}

	t := make([]float64, len(records))
	for i := range t {
		t[i] = 1.0 / float64(pd.SampleRate) * float64(i)
	}
	filter, _ := savitzkygolay.NewFilter(51, 1, 3)
	if hasFront {
		tbins := linspace(0, pd.Front.Calibration.MaxStroke, TRAVEL_HIST_BINS+1)
		dt := digitize(pd.Front.Travel, tbins)

		v, _ := filter.Process(pd.Front.Travel, t)
		pd.Front.Velocity = v
		vbins, dv := digitizeVelocity(v)

		strokes := filterStrokes(v, pd.Rear.Travel, pd.SampleRate)
		pd.Front.Strokes.categorize(strokes, pd.Front.Travel, pd.Front.Calibration.MaxStroke)
		pd.Front.Strokes.histograms(dt, dv, len(vbins))
	}
	if hasRear {
		tbins := linspace(0, pd.Linkage.MaxRearTravel, TRAVEL_HIST_BINS+1)
		dt := digitize(pd.Rear.Travel, tbins)

		v, _ := filter.Process(pd.Rear.Travel, t)
		pd.Rear.Velocity = v
		vbins, dv := digitizeVelocity(v)

		strokes := filterStrokes(v, pd.Rear.Travel, pd.SampleRate)
		pd.Rear.Strokes.categorize(strokes, pd.Rear.Travel, pd.Linkage.MaxRearTravel)
		pd.Rear.Strokes.histograms(dt, dv, len(vbins))
	}

	pd.airtimes()

	return &pd
}
