package psst

import (
	"gonum.org/v1/gonum/stat"
)

func (this *Processed) airtimes() {
	this.Airtimes = make([]*airtime, 0)
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
		maxMean := (this.Linkage.MaxFrontTravel + this.Linkage.MaxRearTravel) / 2.0
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