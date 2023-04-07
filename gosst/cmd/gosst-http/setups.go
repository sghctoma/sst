package main

import (
	"net/http"
	"strconv"

	"github.com/blockloop/scan"
	"github.com/gin-gonic/gin"

	_ "modernc.org/sqlite"

	queries "gosst/internal/db"
)

type setup struct {
	Id               int    `db:"id"                   json:"id" `
	Name             string `db:"name"                 json:"name"              binding:"required"`
	Linkage          int    `db:"linkage_id"           json:"linkage"           binding:"required"`
	FrontCalibration int    `db:"front_calibration_id" json:"front-calibration" binding:"required"`
	RearCalibration  int    `db:"rear_calibration_id"  json:"rear-calibration"  binding:"required"`
}

func (this *RequestHandler) GetSetups(c *gin.Context) {
	rows, err := this.Db.Query(queries.Setups)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var setups []setup
	err = scan.RowsStrict(&setups, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, setups)
}

func (this *RequestHandler) GetSetup(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var setup setup
	rows, err := this.Db.Query(queries.Setup, id)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	err = scan.RowStrict(&setup, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, setup)
}

func (this *RequestHandler) PutSetup(c *gin.Context) {
	var setup setup
	if err := c.ShouldBindJSON(&setup); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	cols := []string{"name", "linkage_id", "front_calibration_id", "rear_calibration_id"}
	vals, _ := scan.Values(cols, &setup)
	var lastInsertedId int
	err := this.Db.QueryRow(queries.InsertSetup, vals...).Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteSetup(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if _, err := this.Db.Exec(queries.DeleteSetup, id); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		c.Status(http.StatusNoContent)
	}
}
