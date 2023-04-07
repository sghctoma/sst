package main

import (
	"net/http"
	"strconv"

	"github.com/blockloop/scan"
	"github.com/gin-gonic/gin"

	_ "modernc.org/sqlite"

	queries "gosst/internal/db"
	psst "gosst/internal/psst"
)

func (this *RequestHandler) GetCalibrations(c *gin.Context) {
	rows, err := this.Db.Query(queries.Calibrations)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var cals []psst.Calibration
	err = scan.RowsStrict(&cals, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	for idx := range cals {
		cals[idx].ProcessRawInputs()
	}

	c.JSON(http.StatusOK, cals)
}

func (this *RequestHandler) GetCalibration(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var cal psst.Calibration
	rows, err := this.Db.Query(queries.Calibration, id)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	err = scan.RowStrict(&cal, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err = cal.ProcessRawInputs(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, cal)
}

func (this *RequestHandler) PutCalibration(c *gin.Context) {
	var cal psst.Calibration
	if err := c.ShouldBindJSON(&cal); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	rows, err := this.Db.Query(queries.CalibrationMethod, cal.MethodId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	var cm psst.CalibrationMethod
	err = scan.RowStrict(&cm, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	cal.Method = cm
	if err = cal.Method.ProcessRawData(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err = cal.Prepare(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err = cal.DumpRawInput(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	cols := []string{"name", "method_id", "inputs"}
	vals, _ := scan.Values(cols, &cal)
	var lastInsertedId int
	if err = this.Db.QueryRow(queries.InsertCalibration, vals...).Scan(&lastInsertedId); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteCalibration(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if _, err := this.Db.Exec(queries.DeleteCalibration, id); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		c.Status(http.StatusNoContent)
	}
}
