package main

import (
	"database/sql"
	"encoding/base64"
	"log"
	"net/http"
	"strconv"

	"github.com/blockloop/scan"
	"github.com/gin-gonic/gin"
	"github.com/ugorji/go/codec"

	_ "modernc.org/sqlite"

	psst "gosst/formats/psst"
	sst "gosst/formats/sst"
	queries "gosst/internal/db"
)

type session struct {
	Id          int    `db:"id"          json:"id"`
	Name        string `db:"name"        json:"name"           binding:"required"`
	Timestamp   int64  `db:"timestamp"   json:"timestamp"`
	Description string `db:"description" json:"description"    binding:"required"`
	Setup       int    `db:"setup_id"    json:"setup"`
	RawData     string `                 json:"data,omitempty" binding:"required"`
	Processed   []byte `db:"data"        json:"-"`
}

func (this *RequestHandler) GetSessions(c *gin.Context) {
	rows, err := this.Db.Query(queries.Sessions)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	var sessions []session
	err = scan.RowsStrict(&sessions, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, sessions)
}

func (this *RequestHandler) GetSession(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	rows, err := this.Db.Query(queries.Session, id)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	var session session
	scan.RowStrict(&session, rows)

	c.JSON(http.StatusOK, session)
}

func (this *RequestHandler) GetSessionData(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var name string
	var data []byte
	err = this.Db.QueryRow(queries.SessionData, id).Scan(&name, &data)
	if err != nil {
		if err == sql.ErrNoRows {
			c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		} else {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		}
		return
	}

	c.Header("Content-Disposition", "attachment; filename="+name)
	c.Data(http.StatusOK, "application/octet-stream", data)
}

func (this *RequestHandler) PutProcessedSession(c *gin.Context) {
	var session session
	if err := c.ShouldBindJSON(&session); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	psst_data, err := base64.StdEncoding.DecodeString(session.RawData)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	var h codec.MsgpackHandle
	dec := codec.NewDecoderBytes(psst_data, &h)
	var processed psst.Processed
	if err := dec.Decode(&processed); err != nil {
		c.AbortWithStatusJSON(http.StatusUnprocessableEntity, gin.H{"error": err.Error()})
		return
	}

	session.Processed = psst_data
	session.Timestamp = processed.Timestamp
	session.Setup = -1

	cols := []string{"name", "timestamp", "description", "setup_id", "data"}
	vals, _ := scan.Values(cols, &session)
	var lastInsertedId int
	if err := this.Db.QueryRow(queries.InsertSession, vals...).Scan(&lastInsertedId); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		this.Channel <- lastInsertedId
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) PutSession(c *gin.Context) {
	var session session
	if err := c.ShouldBindJSON(&session); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	rows, err := this.Db.Query(queries.Setup, session.Setup)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	var setup setup
	err = scan.RowStrict(&setup, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var linkage psst.Linkage
	rows, err = this.Db.Query(queries.Linkage, setup.Linkage)
	err = scan.RowStrict(&linkage, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	err = linkage.ProcessRawData()
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var frontCalibration psst.Calibration
	rows, err = this.Db.Query(queries.Calibration, setup.FrontCalibration)
	err = scan.RowStrict(&frontCalibration, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := frontCalibration.ProcessRawInputs(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	rows, err = this.Db.Query(queries.CalibrationMethod, frontCalibration.MethodId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	frontCalibration.Method = new(psst.CalibrationMethod)
	if err := scan.RowStrict(frontCalibration.Method, rows); err != nil {
		log.Println(err)
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := frontCalibration.Method.ProcessRawData(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := frontCalibration.Prepare(linkage.MaxFrontStroke, linkage.MaxFrontTravel); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var rearCalibration psst.Calibration
	rows, err = this.Db.Query(queries.Calibration, setup.RearCalibration)
	err = scan.RowStrict(&rearCalibration, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := rearCalibration.ProcessRawInputs(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	rows, err = this.Db.Query(queries.CalibrationMethod, rearCalibration.MethodId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	rearCalibration.Method = new(psst.CalibrationMethod)
	if err := scan.RowStrict(rearCalibration.Method, rows); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := rearCalibration.Method.ProcessRawData(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := rearCalibration.Prepare(linkage.MaxRearStroke, linkage.MaxRearTravel); err != nil {
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
		c.AbortWithStatusJSON(http.StatusUnprocessableEntity, gin.H{"error": err.Error()})
		return
	}
	meta.Name = session.Name
	pd, err := psst.ProcessRecording(front, rear, meta, linkage, frontCalibration, rearCalibration)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusUnprocessableEntity, gin.H{"error": err.Error()})
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
	var lastInsertedId int
	if err = this.Db.QueryRow(queries.InsertSession, vals...).Scan(&lastInsertedId); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		this.Channel <- lastInsertedId
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteSession(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if _, err := this.Db.Exec(queries.DeleteSession, id); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		c.Status(http.StatusNoContent)
	}
}

func (this *RequestHandler) PatchSession(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var sessionMeta struct {
		Name        string `json:"name" binding:"required"`
		Description string `json:"desc"`
	}
	if err := c.ShouldBindJSON(&sessionMeta); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if _, err := this.Db.Exec(queries.UpdateSession, sessionMeta.Name, sessionMeta.Description, id); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		c.Status(http.StatusNoContent)
	}
}
