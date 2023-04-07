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

func (this *RequestHandler) GetCalibrationMethods(c *gin.Context) {
	rows, err := this.Db.Query(queries.CalibrationMethods)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	var cms []psst.CalibrationMethod
	err = scan.RowsStrict(&cms, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	for idx := range cms {
		cms[idx].ProcessRawData()
	}

	c.JSON(http.StatusOK, cms)
}

func (this *RequestHandler) GetCalibrationMethod(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	var cm psst.CalibrationMethod
	rows, err := this.Db.Query(queries.CalibrationMethod, id)
	if err != nil {
		c.AbortWithStatus(http.StatusNotFound)
		return
	}
	err = scan.RowStrict(&cm, rows)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}
	if err := cm.ProcessRawData(); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	c.JSON(http.StatusOK, cm)
}

func (this *RequestHandler) PutCalibrationMethod(c *gin.Context) {
	var cm psst.CalibrationMethod
	if err := c.ShouldBindJSON(&cm); err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if err := cm.DumpRawData(); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	if err := cm.Prepare(); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	}

	cols := []string{"name", "description", "data"}
	vals, _ := scan.Values(cols, &cm)
	var lastInsertedId int
	if err := this.Db.QueryRow(queries.InsertCalibrationMethod, vals...).Scan(&lastInsertedId); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteCalibrationMethod(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	if _, err := this.Db.Exec(queries.DeleteCalibrationMethod, id); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}
