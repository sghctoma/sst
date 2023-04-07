package main

import (
	"net/http"

	"github.com/blockloop/scan"
	"github.com/gin-gonic/gin"

	_ "modernc.org/sqlite"

	queries "gosst/internal/db"
)

type board struct {
	Id    string `db:"id"       json:"id"    binding:"required"`
	Setup int    `db:"setup_id" json:"setup" binding:"required"`
}

func (this *RequestHandler) PutBoard(c *gin.Context) {
	var board board
	if err := c.ShouldBindJSON(&board); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	vals, _ := scan.Values([]string{"id", "setup_id"}, &board)
	var lastInsertedId int
	err := this.Db.QueryRow(queries.InsertBoard, vals...).Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteBoard(c *gin.Context) {
	if _, err := this.Db.Exec(queries.DeleteBoard, c.Param("id")); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		c.Status(http.StatusNoContent)
	}
}
