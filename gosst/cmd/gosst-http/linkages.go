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

func (this *RequestHandler) GetLinkages(c *gin.Context) {
	rows, err := this.Db.Query(queries.Linkages)
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
	rows, err := this.Db.Query(queries.Linkage, id)
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

	cols := []string{"name", "head_angle", "raw_lr_data"}
	vals, _ := scan.Values(cols, &linkage)
	var lastInsertedId int
	err := this.Db.QueryRow(queries.InsertLinkage, vals...).Scan(&lastInsertedId)
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		return
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

	if _, err := this.Db.Exec(queries.DeleteLinkage, id); err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
	} else {
		c.Status(http.StatusNoContent)
	}
}
