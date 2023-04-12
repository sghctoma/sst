package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	_ "modernc.org/sqlite"

	queries "gosst/internal/db"
)

type track struct {
	Time []int64   `json:"time" binding:"required"`
	Lat  []float64 `json:"lat" binding:"required"`
	Lon  []float64 `json:"lon" binding:"required"`
	Ele  []float64 `json:"ele" binding:"required"`
}

func (this *RequestHandler) PutTrack(c *gin.Context) {
	var track track
	if err := c.ShouldBindJSON(&track); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	sessionId, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var lastInsertedId int
	trackJson, err := json.Marshal(track)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := this.Db.QueryRow(queries.InsertTrack, string(trackJson)).Scan(&lastInsertedId); err != nil {
		fmt.Println(err)
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if _, err := this.Db.Exec(queries.SetTrackForSession, lastInsertedId, sessionId); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
}
