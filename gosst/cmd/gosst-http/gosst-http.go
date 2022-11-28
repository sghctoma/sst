package main

import (
	"database/sql"
	"encoding/base64"
	"log"
	"math"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/blockloop/scan"
	"github.com/gin-gonic/gin"
	"github.com/ugorji/go/codec"

	_ "modernc.org/sqlite"

	psst "gosst/internal/psst"
	schema "gosst/internal/schema"
)

type setup struct {
	Id               int    `db:"setup_id"             json:"id" `
	Name             string `db:"name"                 json:"name"              binding:"required"`
	Linkage          int    `db:"linkage_id"           json:"linkage"           binding:"required"`
	FrontCalibration int    `db:"front_calibration_id" json:"front-calibration" binding:"required"`
	RearCalibration  int    `db:"rear_calibration_id"  json:"rear-calibration"  binding:"required"`
}

type session struct {
	Id          int    `db:"session_id"  json:"id"`
	Name        string `db:"name"        json:"name"           binding:"required"`
	Timestamp   int64  `db:"timestamp"   json:"timestamp"`
	Description string `db:"description" json:"description"    binding:"required"`
	Setup       int    `db:"setup_id"    json:"setup"          binding:"required"`
	RawData     string `                 json:"data,omitempty" binding:"required"`
	Processed   []byte `db:"data"        json:"-"`
}

type board struct {
	Id    string `db:"board_id" json:"id"    binding:"required"`
	Setup int    `db:"setup_id" json:"setup" binding:"required"`
}

type RequestHandler struct {
	Db *sql.DB
}

func (this *RequestHandler) PutBoard(c *gin.Context) {
	var board board
	if err := c.ShouldBindJSON(&board); err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	cols := []string{"board_id", "setup_id"}
	vals, _ := scan.Values(cols, &board)
	tx, err := this.Db.Begin()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()
	_, err = tx.Exec("INSERT INTO boards ("+strings.Join(cols, ",")+") VALUES (?, ?)", vals...)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	var lastInsertedId int
	err = tx.QueryRow("SELECT last_insert_rowid()").Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	err = tx.Commit()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteBoard(c *gin.Context) {
	if _, err := this.Db.Exec("DELETE FROM boards WHERE board_id = ?", c.Param("id")); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}

func (this *RequestHandler) GetSetups(c *gin.Context) {
	rows, err := this.Db.Query("SELECT * FROM setups")
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	var setups []setup
	err = scan.RowsStrict(&setups, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	c.JSON(http.StatusOK, setups)
}

func (this *RequestHandler) GetSetup(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	var setup setup
	rows, err := this.Db.Query("SELECT * FROM setup WHERE setup_id = ?", id)
	if err != nil {
		c.AbortWithStatus(http.StatusNotFound)
		return
	}
	err = scan.RowStrict(&setup, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	c.JSON(http.StatusOK, setup)
}

func (this *RequestHandler) PutSetup(c *gin.Context) {
	var setup setup
	if err := c.ShouldBindJSON(&setup); err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	cols := []string{"name", "linkage_id", "front_calibration_id", "rear_calibration_id"}
	vals, _ := scan.Values(cols, &setup)
	tx, err := this.Db.Begin()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()
	_, err = tx.Exec("INSERT INTO setups ("+strings.Join(cols, ",")+") VALUES (?, ?, ?, ?)", vals...)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	var lastInsertedId int
	err = tx.QueryRow("SELECT last_insert_rowid()").Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	err = tx.Commit()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteSetup(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if _, err := this.Db.Exec("DELETE FROM setups WHERE setup_id = ?", id); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}

func (this *RequestHandler) GetCalibrations(c *gin.Context) {
	rows, err := this.Db.Query("SELECT * FROM calibrations")
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	var cals []psst.Calibration
	err = scan.RowsStrict(&cals, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	c.JSON(http.StatusOK, cals)
}

func (this *RequestHandler) GetCalibration(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	var cal psst.Calibration
	rows, err := this.Db.Query("SELECT * FROM calibrations where calibration_id = ?", id)
	if err != nil {
		c.AbortWithStatus(http.StatusNotFound)
		return
	}
	err = scan.RowStrict(&cal, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	c.JSON(http.StatusOK, cal)
}

func (this *RequestHandler) PutCalibration(c *gin.Context) {
	var cal psst.Calibration
	if err := c.ShouldBindJSON(&cal); err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}
	if c.Query("lego") == "1" {
		// 1M = 5/16 inch = 7.9375 mm
		cal.ArmLength *= 7.9375
		cal.MaxDistance *= 7.9375
	}
	cal.StartAngle = math.Acos(cal.MaxDistance / 2.0 / cal.ArmLength)

	cols := []string{"name", "arm", "dist", "stroke", "angle"}
	vals, _ := scan.Values(cols, &cal)
	tx, err := this.Db.Begin()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()
	_, err = tx.Exec("INSERT INTO calibrations ("+strings.Join(cols, ",")+") VALUES (?, ?, ?, ?, ?)", vals...)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	var lastInsertedId int
	err = tx.QueryRow("SELECT last_insert_rowid()").Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	err = tx.Commit()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteCalibration(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if _, err := this.Db.Exec("DELETE FROM calibrations WHERE calibration_id = ?", id); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}

func (this *RequestHandler) GetLinkages(c *gin.Context) {
	rows, err := this.Db.Query("SELECT * FROM linkages")
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	var linkages []psst.Linkage
	err = scan.RowsStrict(&linkages, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	for i := range linkages {
		linkages[i].Process()
	}

	c.JSON(http.StatusOK, linkages)
}

func (this *RequestHandler) GetLinkage(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	var linkage psst.Linkage
	rows, err := this.Db.Query("SELECT * FROM linkages where linkage_id = ?", id)
	if err != nil {
		c.AbortWithStatus(http.StatusNotFound)
		return
	}
	err = scan.RowStrict(&linkage, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	if linkage.Process() != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	c.JSON(http.StatusOK, linkage)
}

func (this *RequestHandler) PutLinkage(c *gin.Context) {
	var linkage psst.Linkage
	if err := c.ShouldBindJSON(&linkage); err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if linkage.Process() != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	cols := []string{"name", "raw_lr_data"}
	vals, _ := scan.Values(cols, &linkage)
	tx, err := this.Db.Begin()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()
	_, err = tx.Exec("INSERT INTO linkages ("+strings.Join(cols, ",")+") VALUES (?, ?)", vals...)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	var lastInsertedId int
	err = tx.QueryRow("SELECT last_insert_rowid()").Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	err = tx.Commit()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteLinkage(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if _, err := this.Db.Exec("DELETE FROM linkages WHERE linkage_id = ?", id); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}

func (this *RequestHandler) GetSessions(c *gin.Context) {
	rows, err := this.Db.Query("SELECT session_id, name, timestamp, description, setup_id FROM sessions")
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	var sessions []session
	err = scan.RowsStrict(&sessions, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	c.JSON(http.StatusOK, sessions)
}

func (this *RequestHandler) GetSession(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	rows, err := this.Db.Query("SELECT session_id, name, timestamp, description, setup_id FROM sessions where session_id = ?", id)
	if err != nil {
		c.AbortWithStatus(http.StatusNotFound)
		return
	}
	var session session
	scan.RowStrict(&session, rows)

	c.JSON(http.StatusOK, session)
}

func (this *RequestHandler) GetSessionData(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	var name string
	var data []byte
	err = this.Db.QueryRow("SELECT name, data FROM sessions where session_id = ?", id).Scan(&name, &data)
	if err != nil {
		if err == sql.ErrNoRows {
			c.AbortWithStatus(http.StatusNotFound)
		} else {
			c.AbortWithStatus(http.StatusInternalServerError)
		}
		return
	}

	c.Header("Content-Disposition", "attachment; filename="+name)
	c.Data(http.StatusOK, "application/octet-stream", data)
}

func (this *RequestHandler) PutSession(c *gin.Context) {
	var session session
	if err := c.ShouldBindJSON(&session); err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	rows, err := this.Db.Query("SELECT * FROM setups WHERE setup_id = ?", session.Setup)
	if err != nil {
		c.AbortWithStatus(http.StatusNotFound)
		return
	}
	var setup setup
	err = scan.RowStrict(&setup, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	var frontCalibration, rearCalibration psst.Calibration
	rows, err = this.Db.Query("SELECT * FROM calibrations WHERE calibration_id = ?", setup.FrontCalibration)
	err = scan.RowStrict(&frontCalibration, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	rows, err = this.Db.Query("SELECT * FROM calibrations WHERE calibration_id = ?", setup.RearCalibration)
	err = scan.RowStrict(&rearCalibration, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	var linkage psst.Linkage
	rows, err = this.Db.Query("SELECT * FROM linkages WHERE linkage_id = ?", setup.Linkage)
	err = scan.RowStrict(&linkage, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	err = linkage.Process()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	sst, err := base64.StdEncoding.DecodeString(session.RawData)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}
	pd := psst.ProcessRecording(sst, session.Name, linkage, frontCalibration, rearCalibration)
	if pd == nil {
		c.AbortWithStatus(http.StatusUnprocessableEntity)
		return
	}

	var data []byte
	var h codec.MsgpackHandle
	enc := codec.NewEncoderBytes(&data, &h)
	enc.Encode(pd)
	session.Processed = data
	session.Timestamp = pd.Timestamp

	cols := []string{"name", "timestamp", "description", "setup_id", "data"}
	vals, _ := scan.Values(cols, &session)
	tx, err := this.Db.Begin()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()
	_, err = tx.Exec("INSERT INTO sessions ("+strings.Join(cols, ",")+") VALUES (?, ?, ?, ?, ?)", vals...)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	var lastInsertedId int
	err = tx.QueryRow("SELECT last_insert_rowid()").Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	err = tx.Commit()
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteSession(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if _, err := this.Db.Exec("DELETE FROM sessions WHERE session_id = ?", id); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}

func (this *RequestHandler) PatchSession(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	var sessionMeta struct {
		Name        string `json:"name" binding:"required"`
		Description string `json:"desc"`
	}
	if err := c.ShouldBindJSON(&sessionMeta); err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if _, err := this.Db.Exec("UPDATE sessions SET (name, description) = (?, ?) WHERE session_id = ?",
		sessionMeta.Name, sessionMeta.Description, id); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}

func main() {
	db, err := sql.Open("sqlite", os.Args[1])
	if err != nil {
		log.Fatal("could not open database")
	}
	if _, err := db.Exec(schema.Sql); err != nil {
		log.Fatal("could not create data tables")
	}

	//XXX gin.SetMode(gin.ReleaseMode)
	router := gin.Default()
	router.SetTrustedProxies(nil)

	router.GET("/calibrations", (&RequestHandler{Db: db}).GetCalibrations)
	router.GET("/calibration/:id", (&RequestHandler{Db: db}).GetCalibration)
	router.PUT("/calibration", (&RequestHandler{Db: db}).PutCalibration)
	router.DELETE("/calibration/:id", (&RequestHandler{Db: db}).DeleteCalibration)

	router.GET("/linkages", (&RequestHandler{Db: db}).GetLinkages)
	router.GET("/linkage/:id", (&RequestHandler{Db: db}).GetLinkage)
	router.PUT("/linkage", (&RequestHandler{Db: db}).PutLinkage)
	router.DELETE("/linkage/:id", (&RequestHandler{Db: db}).DeleteLinkage)

	router.GET("/setups", (&RequestHandler{Db: db}).GetSetups)
	router.GET("/setup/:id", (&RequestHandler{Db: db}).GetSetup)
	router.PUT("/setup", (&RequestHandler{Db: db}).PutSetup)
	router.DELETE("/setup/:id", (&RequestHandler{Db: db}).DeleteSetup)

	router.PUT("/board", (&RequestHandler{Db: db}).PutBoard)
	router.DELETE("/board/:id", (&RequestHandler{Db: db}).DeleteBoard)

	router.GET("/sessions", (&RequestHandler{Db: db}).GetSessions)
	router.GET("/session/:id", (&RequestHandler{Db: db}).GetSession)
	router.GET("/sessiondata/:id", (&RequestHandler{Db: db}).GetSessionData)
	router.PUT("/session", (&RequestHandler{Db: db}).PutSession)
	router.DELETE("/session/:id", (&RequestHandler{Db: db}).DeleteSession)
	router.PATCH("/session/:id", (&RequestHandler{Db: db}).PatchSession)

	router.Run("127.0.0.1:8080")
}
