package main

import (
	"log"
	"math"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/syndtr/goleveldb/leveldb"
	"github.com/syndtr/goleveldb/leveldb/util"
	"github.com/ugorji/go/codec"
)

type session struct {
    Date        time.Time `codec:"," json:"date"`
    Name        string    `codec:"," json:"path"`
    Description string    `codec:"," json:"description"`
    Data        processed `codec:"," json:"-"`
}

type calibrationPair struct {
    Name  string      `codec:"," json:"name" binding:"required"`
    Front calibration `codec:"," json:"front" validate:"dive" binding:"required"`
    Rear  calibration `codec:"," json:"rear" validate:"dive" binding:"required"`
}

type RequestHandler struct {
    Db *leveldb.DB
    H codec.Handle
}

func (this *RequestHandler) GetCalibrations(c *gin.Context) {
    m := make(map[string]calibrationPair)
    iter := this.Db.NewIterator(util.BytesPrefix([]byte("cal-")), nil)
    for iter.Next() {
        dec := codec.NewDecoderBytes(iter.Value(), this.H)
        var cal calibrationPair
        dec.Decode(&cal)
        m[string(iter.Key()[:])] = cal
    }
    iter.Release()
    c.JSON(http.StatusOK, m)
}

func (this *RequestHandler) GetCalibration(c *gin.Context) {
    b, err := this.Db.Get([]byte("cal-" + c.Param("id")), nil)
    if err != nil {
        c.AbortWithStatus(http.StatusNotFound)
        return
    }

    dec := codec.NewDecoderBytes(b, this.H)
    var cal calibrationPair
    dec.Decode(&cal)
    c.JSON(http.StatusOK, cal)
}

func (this *RequestHandler) PutCalibration(c *gin.Context) {
    var calibration calibrationPair
    if err := c.ShouldBindJSON(&calibration); err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    if c.Query("lego") == "1" {
        // 1M = 5/16 inch = 7.9375 mm
        calibration.Front.ArmLength *= 7.9375
        calibration.Front.MaxDistance *= 7.9375
        calibration.Rear.ArmLength *= 7.9375
        calibration.Rear.MaxDistance *= 7.9375
    }
    calibration.Front.StartAngle = math.Acos(calibration.Front.MaxDistance / 2.0 / calibration.Front.ArmLength)
    calibration.Rear.StartAngle = math.Acos(calibration.Rear.MaxDistance / 2.0 / calibration.Rear.ArmLength)
    var b []byte
    enc := codec.NewEncoderBytes(&b, this.H)
    enc.Encode(calibration)

    id := uuid.NewString()
    if err := this.Db.Put([]byte("cal-" + id), b, nil); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.JSON(http.StatusCreated, gin.H{"id": id})
    }
}

func (this *RequestHandler) DeleteCalibration (c *gin.Context) {
    if err := this.Db.Delete([]byte("cal-" + c.Param("id")), nil); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusNoContent)
    }
}

func (this *RequestHandler) GetLinkages(c *gin.Context) {
    m := make(map[string]linkage)
    iter := this.Db.NewIterator(util.BytesPrefix([]byte("lnk-")), nil)
    for iter.Next() {
        dec := codec.NewDecoderBytes(iter.Value(), this.H)
        var linkage linkage
        dec.Decode(&linkage)
        m[string(iter.Key()[:])] = linkage
    }
    iter.Release()
    c.JSON(http.StatusOK, m)
}

func (this *RequestHandler) GetLinkage(c *gin.Context) {
    b, err := this.Db.Get([]byte("lnk-" + c.Param("id")), nil)
    if err != nil {
        c.AbortWithStatus(http.StatusNotFound)
        return
    }

    dec := codec.NewDecoderBytes(b, this.H)
    var linkage linkage
    dec.Decode(&linkage)
    c.JSON(http.StatusOK, linkage)
}

func (this *RequestHandler) PutLinkage(c *gin.Context) {
    name := c.PostForm("name")
    file, _ := c.FormFile("leverage")
    f, _ := file.Open()
    linkage := newLinkage(name, f)
    var b []byte
    enc := codec.NewEncoderBytes(&b, this.H)
    enc.Encode(linkage)

    id := uuid.NewString()
    if err := this.Db.Put([]byte("lnk-" + id), b, nil); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.JSON(http.StatusCreated, gin.H{"id": id})
    }
}

func (this *RequestHandler) DeleteLinkage(c *gin.Context) {
    if err := this.Db.Delete([]byte("lnk-" + c.Param("id")), nil); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusNoContent)
    }
}

func (this *RequestHandler) GetSessions(c *gin.Context) {
    m := make(map[string]session)
    iter := this.Db.NewIterator(util.BytesPrefix([]byte("ses-")), nil)
    for iter.Next() {
        dec := codec.NewDecoderBytes(iter.Value(), this.H)
        var session session
        dec.Decode(&session)
        m[string(iter.Key()[:])] = session
    }
    iter.Release()
    c.JSON(http.StatusOK, m)
}

func (this *RequestHandler) GetSession(c *gin.Context) {
    b, err := this.Db.Get([]byte("ses-" + c.Param("id")), nil)
    if err != nil {
        c.AbortWithStatus(http.StatusNotFound)
        return
    }

    dec := codec.NewDecoderBytes(b, this.H)
    var session session
    dec.Decode(&session)
    c.JSON(http.StatusOK, session)
}

func (this *RequestHandler) GetSessionData(c *gin.Context) {
    bs, err := this.Db.Get([]byte("ses-" + c.Param("id")), nil)
    if err != nil {
        c.AbortWithStatus(http.StatusNotFound)
        return
    }

    dec := codec.NewDecoderBytes(bs, this.H)
    var session session
    dec.Decode(&session)

    var bd []byte
    enc := codec.NewEncoderBytes(&bd, this.H)
    enc.Encode(session.Data)
    c.Header("Content-Disposition", "attachment; filename=" + session.Name)
    c.Data(http.StatusOK, "application/octet-stream", bd)
}

func (this *RequestHandler) PutSession(c *gin.Context) {
    var cpair calibrationPair
    bc, err := this.Db.Get([]byte("cal-" + c.PostForm("calibration")), nil)
    if err != nil {
        c.AbortWithStatus(http.StatusNotFound)
        return
    }
    cdec := codec.NewDecoderBytes(bc, this.H)
    cdec.Decode(&cpair)

    var linkage linkage
    bl, err := this.Db.Get([]byte("lnk-" + c.PostForm("linkage")), nil)
    if err != nil {
        c.AbortWithStatus(http.StatusNotFound)
        return
    }
    ldec := codec.NewDecoderBytes(bl, this.H)
    ldec.Decode(&linkage)

    file, _ := c.FormFile("recording")
    pd := prorcessRecording(file, linkage, cpair.Front, cpair.Rear)
    if pd == nil {
        c.AbortWithStatus(http.StatusUnprocessableEntity)
        return
    }

    var bs []byte
    enc := codec.NewEncoderBytes(&bs, this.H)
    enc.Encode(&session{
        Date: time.Now(),
        Name: pd.Name,
        Description: c.PostForm("description"),
        Data: *pd,
    })

    id := uuid.NewString()
    if err := this.Db.Put([]byte("ses-" + id), bs, nil); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.JSON(http.StatusCreated, gin.H{"id": id})
    }
}

func (this *RequestHandler) DeleteSession(c *gin.Context) {
    if err := this.Db.Delete([]byte("ses-" + c.Param("id")), nil); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusNoContent)
    }
}

func main() {
    var h codec.MsgpackHandle

    db, err := leveldb.OpenFile("data/gosst.db", nil)
    if err != nil {
        log.Fatal("could not open database")
    }
    defer db.Close()

    //XXX gin.SetMode(gin.ReleaseMode)
    router := gin.Default()
    router.SetTrustedProxies(nil)

    router.GET("/calibrations", (&RequestHandler{Db: db, H: &h}).GetCalibrations)
    router.GET("/calibration/:id", (&RequestHandler{Db: db, H: &h}).GetCalibration)
    router.PUT("/calibration", (&RequestHandler{Db: db, H: &h}).PutCalibration)
    router.DELETE("/calibration/:id", (&RequestHandler{Db: db, H: &h}).DeleteCalibration)

    router.GET("/linkages", (&RequestHandler{Db: db, H: &h}).GetLinkages)
    router.GET("/linkage/:id", (&RequestHandler{Db: db, H: &h}).GetLinkage)
    router.PUT("/linkage", (&RequestHandler{Db: db, H: &h}).PutLinkage)
    router.DELETE("/linkage/:id", (&RequestHandler{Db: db, H: &h}).DeleteLinkage)

    router.GET("/sessions", (&RequestHandler{Db: db, H: &h}).GetSessions)
    router.GET("/session/:id", (&RequestHandler{Db: db, H: &h}).GetSession)
    router.GET("/sessiondata/:id", (&RequestHandler{Db: db, H: &h}).GetSessionData)
    router.PUT("/session", (&RequestHandler{Db: db, H: &h}).PutSession)
    router.DELETE("/session/:id", (&RequestHandler{Db: db, H: &h}).DeleteSession)

    router.Run("127.0.0.1:8080")
}
