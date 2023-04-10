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

func (this *RequestHandler) GetLinkages(c *gin.Context) {
	rows, err := this.Db.Query(queries.Linkages)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	var linkages []psst.Linkage
	err = scan.RowsStrict(&linkages, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
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
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var linkage psst.Linkage
	rows, err := this.Db.Query(queries.Linkage, id)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	err = scan.RowStrict(&linkage, rows)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if linkage.Process() != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, linkage)
}

func (this *RequestHandler) PutLinkage(c *gin.Context) {
	var linkage psst.Linkage
	if err := c.ShouldBindJSON(&linkage); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := linkage.Process(); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	cols := []string{"name", "head_angle", "raw_lr_data"}
	vals, _ := scan.Values(cols, &linkage)
	var lastInsertedId int
	err := this.Db.QueryRow(queries.InsertLinkage, vals...).Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	} else {
		c.JSON(http.StatusCreated, gin.H{"id": lastInsertedId})
	}
}

func (this *RequestHandler) DeleteLinkage(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if _, err := this.Db.Exec(queries.DeleteLinkage, id); err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else {
		c.Status(http.StatusNoContent)
	}
}
