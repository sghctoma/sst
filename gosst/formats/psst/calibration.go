package psst

import (
	"encoding/json"
	"github.com/antonmedv/expr"
	"github.com/antonmedv/expr/vm"
	"math"
)

type calibrationMethodParams struct {
	Inputs        []string          `codec:"," json:"inputs"        binding:"required"`
	Intermediates map[string]string `codec:"," json:"intermediates" binding:"required"`
	Expression    string            `codec:"," json:"expression"    binding:"required"`
}

type CalibrationMethod struct {
	Id          int    `codec:"-" db:"id"            json:"id"`
	Name        string `codec:"," db:"name"          json:"name"          binding:"required"`
	Description string `codec:"," db:"description"   json:"description"`
	RawData     string `codec:"-" db:"data"          json:"-"`
	calibrationMethodParams
	program *vm.Program
}

type Calibration struct {
	Id        int                `codec:"-" db:"id"        json:"id"`
	Name      string             `codec:"," db:"name"      json:"name"      binding:"required"`
	MethodId  int                `codec:"," db:"method_id" json:"method_id" binding:"required"`
	RawInputs string             `codec:"-" db:"inputs"    json:"-"`
	Inputs    map[string]float64 `codec:","                json:"inputs"    binding:"required"`
	Method    *CalibrationMethod `codec:"-"                json:"method,omitempty"`
	env       map[string]interface{}
}

type calibrations struct {
	FrontCalibration *Calibration `json:"front"`
	RearCalibration  *Calibration `json:"rear"`
}

var stdenv = map[string]interface{}{
	"pi":     math.Pi,
	"sin":    math.Sin,
	"cos":    math.Cos,
	"tan":    math.Tan,
	"asin":   math.Asin,
	"acos":   math.Acos,
	"atan":   math.Atan,
	"sqrt":   math.Sqrt,
	"sample": 0,
}

func (this *CalibrationMethod) calculateIntermediates(env map[string]interface{}) error {
	for k, v := range this.Intermediates {
		p, err := expr.Compile(v, expr.Env(env))
		if err != nil {
			return err
		}

		out, err := expr.Run(p, env)
		if err != nil {
			return err
		}

		env[k] = out.(float64)
	}

	return nil
}

func (this *CalibrationMethod) ProcessRawData() error {
	if err := json.Unmarshal([]byte(this.RawData), &this.calibrationMethodParams); err != nil {
		return err
	}

	return nil
}

func (this *CalibrationMethod) DumpRawData() error {
	rd, err := json.Marshal(this.calibrationMethodParams)
	if err != nil {
		return err
	}

	this.RawData = string(rd)
	return nil
}

func (this *CalibrationMethod) Prepare() error {
	env := map[string]interface{}{}
	// Copy standard environment
	for k, v := range stdenv {
		env[k] = v
	}

	// Set dummy input values
	for _, input := range this.Inputs {
		env[input] = 0.0
	}
	env["MAX_STROKE"] = 0
	env["MAX_TRAVEL"] = 0

	if err := this.calculateIntermediates(env); err != nil {
		return err
	}

	program, err := expr.Compile(this.Expression, expr.Env(env))
	if err != nil {
		return err
	}
	this.program = program

	return nil
}

func (this *Calibration) ProcessRawInputs() error {
	if err := json.Unmarshal([]byte(this.RawInputs), &this.Inputs); err != nil {
		return err
	}

	return nil
}

func (this *Calibration) DumpRawInput() error {
	rd, err := json.Marshal(this.Inputs)
	if err != nil {
		return err
	}

	this.RawInputs = string(rd)
	return nil
}

func (this *Calibration) Prepare(maxStroke, maxTravel float64) error {
	err := this.Method.Prepare()
	if err != nil {
		return err
	}

	this.env = map[string]interface{}{}
	// Copy standard environment
	for k, v := range stdenv {
		this.env[k] = v
	}

	// Set input values
	for k, v := range this.Inputs {
		this.env[k] = v
	}
	this.env["MAX_STROKE"] = maxStroke
	this.env["MAX_TRAVEL"] = maxTravel

	// Calculate intermediates using the inputs
	if err = this.Method.calculateIntermediates(this.env); err != nil {
		return err
	}

	return nil
}

func (this *Calibration) Evaluate(sample float64) (float64, error) {
	this.env["sample"] = sample
	out, err := expr.Run(this.Method.program, this.env)
	if err != nil {
		return math.NaN(), err
	}

	return out.(float64), nil
}

func LoadCalibrations(data []byte, linkage Linkage) (*Calibration, *Calibration, error) {
	var cs calibrations
	if err := json.Unmarshal(data, &cs); err != nil {
		return nil, nil, err
	}
	if cs.FrontCalibration != nil {
		if err := cs.FrontCalibration.Prepare(linkage.MaxFrontStroke, linkage.MaxFrontTravel); err != nil {
			return nil, nil, err
		}
	}
	if cs.RearCalibration != nil {
		if err := cs.RearCalibration.Prepare(linkage.MaxRearStroke, linkage.MaxRearTravel); err != nil {
			return nil, nil, err
		}
	}

	return cs.FrontCalibration, cs.RearCalibration, nil
}
