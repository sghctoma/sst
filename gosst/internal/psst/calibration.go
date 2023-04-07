package psst

import (
	"encoding/json"
	"github.com/antonmedv/expr"
	"github.com/antonmedv/expr/vm"
	"math"
)

type calibrationModeParams struct {
	Inputs        []string          `codec:"," json:"inputs"        binding:"required"`
	Intermediates map[string]string `codec:"," json:"intermediates" binding:"required"`
	Expression    string            `codec:"," json:"expression"    binding:"required"`
}

type CalibrationMethod struct {
	Id          int    `codec:"-" db:"id"            json:"id"`
	Name        string `codec:"," db:"name"          json:"name"          binding:"required"`
	Description string `codec:"," db:"description"   json:"description"`
	RawData     string `codec:"-" db:"data"          json:"-"`
	calibrationModeParams
	program *vm.Program
}

type Calibration struct {
	Id        int                `codec:"-" db:"id"        json:"id"`
	Name      string             `codec:"," db:"name"      json:"name"   binding:"required"`
	MethodId  int                `codec:"," db:"method_id" json:"method" binding:"required"`
	RawInputs string             `codec:"-" db:"inputs"    json:"-"`
	Inputs    map[string]float64 `codec:","                json:"inputs" binding:"required"`
	Method    CalibrationMethod  `codec:"-"                json:"-"`
	env       map[string]interface{}
}

var stdenv = map[string]interface{}{
	"pi":     math.Pi,
	"sin":    math.Sin,
	"cos":    math.Cos,
	"tan":    math.Tan,
	"asin":   math.Asin,
	"acos":   math.Acos,
	"atan":   math.Atan,
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
	if err := json.Unmarshal([]byte(this.RawData), &this.calibrationModeParams); err != nil {
		return err
	}

	return nil
}

func (this *CalibrationMethod) DumpRawData() error {
	rd, err := json.Marshal(this.calibrationModeParams)
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

func (this *Calibration) Prepare() error {
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
