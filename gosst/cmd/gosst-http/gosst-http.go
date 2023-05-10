package main

import (
	"database/sql"
	"encoding/base64"
	"encoding/csv"
	"log"
	"net/http"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/jessevdk/go-flags"

	_ "modernc.org/sqlite"

	psst "gosst/formats/psst"
	sst "gosst/formats/sst"
	common "gosst/internal/common"
	queries "gosst/internal/db"
)

type RequestHandler struct {
	Db        *sql.DB
	ApiServer string
}

type session struct {
	Name        string `json:"name"           binding:"required"`
	Description string `json:"description"`
	Setup       int    `json:"setup"          binding:"required"`
	RawData     string `json:"data,omitempty" binding:"required"`
}

type normalizedSession struct {
	Name        string `json:"name"           binding:"required"`
	Timestamp   int64  `json:"timestamp"      binding:"required"`
	Description string `json:"description"`
	SampleRate  uint16 `json:"sample_rate"    binding:"required"`
	Linkage     int    `json:"linkage"        binding:"required"`
	RawData     string `json:"data,omitempty" binding:"required"`
}

func processNormalized(data string) ([]float64, []float64, error) {
	reader := csv.NewReader(strings.NewReader(data))
	reader.Comma = ';'
	csv_header, err := reader.Read()
	if err != nil {
		return nil, nil, err
	}
	var forkColumn = -1
	var shockColumn = -1
	for i, v := range csv_header {
		if v == "Fork" {
			forkColumn = i
		}
		if v == "Shock" {
			shockColumn = i
		}
	}
	if forkColumn == -1 && shockColumn == -1 {
		return nil, nil, err
	}

	rows, err := reader.ReadAll()
	if err != nil {
		return nil, nil, err
	}

	// If there are samples larger than 1, we treat the dataset as percentage values
	percentage := false
	for idx := range rows {
		if forkColumn != -1 {
			f, _ := strconv.ParseFloat(rows[idx][forkColumn], 64)
			if f > 1 {
				percentage = true
				break
			}
		}
		if shockColumn != -1 {
			r, _ := strconv.ParseFloat(rows[idx][shockColumn], 64)
			if r > 1 {
				percentage = true
				break
			}
		}
	}

	var front, rear []float64
	for idx := range rows {
		if forkColumn != -1 {
			f, _ := strconv.ParseFloat(rows[idx][forkColumn], 64)
			if percentage {
				f /= 100.0
			}
			front = append(front, f)
		}
		if shockColumn != -1 {
			r, _ := strconv.ParseFloat(rows[idx][shockColumn], 64)
			if percentage {
				r /= 100.0
			}
			rear = append(rear, r)
		}
	}

	return front, rear, nil
}

func (this *RequestHandler) PutSession(c *gin.Context) {
	var session session
	if err := c.ShouldBindJSON(&session); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var setupId, linkageId, frontCalibrationId, rearCalibrationId int
	err := this.Db.QueryRow(queries.Setup, session.Setup).Scan(&linkageId, &frontCalibrationId, &rearCalibrationId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	setup, err := common.GetSetupsForIds(this.Db, linkageId, frontCalibrationId, rearCalibrationId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	sst_data, err := base64.StdEncoding.DecodeString(session.RawData)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	front, rear, meta, err := sst.ProcessRaw(sst_data)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	meta.Name = session.Name
	pd, err := psst.ProcessRecording(front, rear, meta, setup)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	lastInsertedId, err := common.InsertSession(this.Db, pd, this.ApiServer, session.Name, session.Description, setupId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
}

func (this *RequestHandler) PutNormalizedSession(c *gin.Context) {
	var session normalizedSession
	if err := c.ShouldBindJSON(&session); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	linkage, err := common.GetLinkage(this.Db, session.Linkage)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	method := psst.CalibrationMethod{Name: "fraction"}
	method.Inputs = []string{}
	method.Intermediates = map[string]string{}
	method.Expression = "sample * MAX_STROKE"
	fcal := &psst.Calibration{
		Name:   "Fraction",
		Method: &method,
		Inputs: map[string]float64{},
	}
	if err := fcal.Prepare(linkage.MaxFrontStroke, linkage.MaxFrontTravel); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	rcal := &psst.Calibration{
		Name:   "Fraction",
		Method: &method,
		Inputs: map[string]float64{},
	}
	if err := rcal.Prepare(linkage.MaxRearStroke, linkage.MaxRearTravel); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	front, rear, err := processNormalized(session.RawData)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	meta := psst.Meta{
		Name:       session.Name,
		Version:    255,
		SampleRate: session.SampleRate,
		Timestamp:  session.Timestamp,
	}
	setup := &psst.SetupData{
		Linkage:          linkage,
		FrontCalibration: fcal,
		RearCalibration:  rcal,
	}
	pd, err := psst.ProcessRecording(front, rear, meta, setup)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	lastInsertedId, err := common.InsertSession(this.Db, pd, this.ApiServer, session.Name, session.Description, 0)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
}

func main() {
	var opts struct {
		DatabaseFile string `short:"d" long:"database" description:"SQLite3 database file path" required:"true"`
		Host         string `short:"h" long:"host" description:"Host to bind on" default:"127.0.0.1"`
		Port         string `short:"p" long:"port" description:"Port to bind on" default:"8080"`
		ApiServer    string `short:"s" long:"server" description:"HTTP API server" default:"http://localhost:5000"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	db, err := sql.Open("sqlite", opts.DatabaseFile)
	if err != nil {
		log.Fatalln("[ERR] could not open database")
	}

	rh := RequestHandler{Db: db, ApiServer: opts.ApiServer}
	//XXX gin.SetMode(gin.ReleaseMode)
	router := gin.Default()
	router.SetTrustedProxies(nil)

	router.PUT("/api/internal/session", rh.PutSession)
	router.PUT("/api/internal/session/normalized", rh.PutNormalizedSession)

	router.Run(opts.Host + ":" + opts.Port)
}
