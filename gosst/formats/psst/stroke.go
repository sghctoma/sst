package psst

import (
	"math"
	"sort"

	"gonum.org/v1/gonum/floats"
)

type strokestat struct {
	SumTravel   float64
	MaxTravel   float64
	SumVelocity float64
	MaxVelocity float64
	Bottomouts  int
	Count       int
}

type stroke struct {
	Start             int
	End               int
	Stat              strokestat
	DigitizedTravel   []int
	DigitizedVelocity []int
	length            float64
	duration          float64
	airCandidate      bool
}

type strokes struct {
	Compressions []*stroke
	Rebounds     []*stroke
	idlings      []*stroke
}

type airtime struct {
	Start float64
	End   float64
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

func sign(v float64) int8 {
	if math.Abs(v) <= VELOCITY_ZERO_THRESHOLD {
		return 0
	} else if math.Signbit(v) {
		return -1
	} else {
		return 1
	}
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

func (this *stroke) overlaps(other *stroke) bool {
	l := max(this.End-this.Start, other.End-other.Start)
	s := max(this.Start, other.Start)
	e := min(this.End, other.End)
	return float32(e-s) >= AIRTIME_OVERLAP_THRESHOLD*float32(l)
}

func newStroke(start, end int, duration float64, travel, velocity []float64, maxTravel float64) *stroke {
	s := &stroke{
		Start:    start,
		End:      end,
		length:   travel[end] - travel[start],
		duration: duration,
	}
	// Maximum velocity for rebound strokes are actually minimum velocity.
	var mv float64
	if s.length < 0 {
		mv = floats.Min(velocity[start : end+1])
	} else {
		mv = floats.Max(velocity[start : end+1])
	}
	bo := 0
	for i := start; i <= end; i++ {
		if travel[i] > maxTravel-BOTTOMOUT_THRESHOLD {
			bo += 1
			for ; travel[i] > maxTravel-BOTTOMOUT_THRESHOLD; i++ {
			}
		}
	}
	stat := strokestat{
		SumTravel:   floats.Sum(travel[start : end+1]),
		MaxTravel:   floats.Max(travel[start : end+1]),
		SumVelocity: floats.Sum(velocity[start : end+1]),
		MaxVelocity: mv,
		Bottomouts:  bo,
		Count:       end - start + 1,
	}
	s.Stat = stat
	return s
}

func (this *strokes) categorize(strokes []*stroke, travel []float64, maxTravel float64) {
	this.Compressions = make([]*stroke, 0)
	this.Rebounds = make([]*stroke, 0)
	for i, stroke := range strokes {
		if math.Abs(stroke.length) < STROKE_LENGTH_THRESHOLD &&
			stroke.duration >= IDLING_DURATION_THRESHOLD {

			// If suitable, tag this idling stroke as possible airtime.
			// Whether or not it really is one, will be decided with
			// further heuristics based on both front and read
			// candidates.
			if i > 0 && i < len(strokes)-1 &&
				stroke.Stat.MaxTravel <= STROKE_LENGTH_THRESHOLD &&
				stroke.duration >= AIRTIME_DURATION_THRESHOLD &&
				strokes[i+1].Stat.MaxVelocity >= AIRTIME_VELOCITY_THRESHOLD {

				stroke.airCandidate = true
			}
			this.idlings = append(this.idlings, stroke)
		} else if stroke.length >= STROKE_LENGTH_THRESHOLD {
			this.Compressions = append(this.Compressions, stroke)
		} else if stroke.length <= -STROKE_LENGTH_THRESHOLD {
			this.Rebounds = append(this.Rebounds, stroke)
		}
	}
}

func (this *strokes) digitize(dt, dv []int) {
	for _, s := range this.Compressions {
		s.DigitizedTravel = dt[s.Start : s.End+1]
		s.DigitizedVelocity = dv[s.Start : s.End+1]
	}
	for _, s := range this.Rebounds {
		s.DigitizedTravel = dt[s.Start : s.End+1]
		s.DigitizedVelocity = dv[s.Start : s.End+1]
	}
}

func filterStrokes(velocity, travel []float64, maxTravel float64, rate uint16) (strokes []*stroke) {
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
			strokes[len(strokes)-1].Stat.MaxTravel < STROKE_LENGTH_THRESHOLD {

			strokes[len(strokes)-1].End = i
			strokes[len(strokes)-1].duration += d
		} else {
			s := newStroke(start_index, i, d, travel, velocity, maxTravel)
			strokes = append(strokes, s)
		}
	}

	return strokes
}
