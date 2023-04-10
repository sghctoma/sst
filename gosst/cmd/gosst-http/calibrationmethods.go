package main

import (
	"net/http"
	"strconv"

	"github.com/blockloop/scan"
	"github.com/gin-gonic/gin"

	_ "modernc.org/sqlite"

	psst "gosst/formats/psst"
	queries "gosst/internal/db"
)

func (this *RequestHandler) GetCalibrationMethods(c *gin.Context) {
	rows, err := this.Db.Query(queries.CalibrationMethods)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var cms []psst.CalibrationMethod
	err = scan.RowsStrict(&cms, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
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
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var cm psst.CalibrationMethod
	rows, err := this.Db.Query(queries.CalibrationMethod, id)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	err = scan.RowStrict(&cm, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := cm.ProcessRawData(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, cm)
}

func (this *RequestHandler) PutCalibrationMethod(c *gin.Context) {
	var cm psst.CalibrationMethod
	if err := c.ShouldBindJSON(&cm); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := cm.DumpRawData(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err := cm.Prepare(); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	cols := []string{"name", "description", "data"}
	vals, _ := scan.Values(cols, &cm)
	var lastInsertedId int
	if err := this.Db.QueryRow(queries.InsertCalibrationMethod, vals...).Scan(&lastInsertedId); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteCalibrationMethod(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if _, err := this.Db.Exec(queries.DeleteCalibrationMethod, id); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		c.Status(http.StatusNoContent)
	}
}
