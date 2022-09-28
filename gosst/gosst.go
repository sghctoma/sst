package main

import (
	"encoding/binary"
	"fmt"
	"math"
	"net/http"
	"os"
	"path"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/ugorji/go/codec"
	"go.etcd.io/bbolt"
)

type session struct {
    Date        time.Time `json:"date"`
    Path        string    `json:"path"`
    Description string    `json:"description"`
}

type calibrationPair struct {
    Name  string      `json:"name" binding:"required"`
    Front calibration `json:"front" validate:"dive" binding:"required"`
    Rear  calibration `json:"rear" validate:"dive" binding:"required"`
}

// itob returns an 8-byte big endian representation of v.
func itob(v uint64) []byte {
    b := make([]byte, 8)
    binary.BigEndian.PutUint64(b, uint64(v))
    return b
}

type RequestHandler struct {
    Db *bbolt.DB
    H codec.Handle
}

func (this *RequestHandler) GetCalibrations(c *gin.Context) {
    this.Db.View(func(tx *bbolt.Tx) error {
        m := make(map[uint64]calibrationPair)
        b := tx.Bucket([]byte("calibrations"))
        cur := b.Cursor()
        for k, v := cur.First(); k != nil; k, v = cur.Next() {
            dec := codec.NewDecoderBytes(v, this.H)
            var cal calibrationPair
            dec.Decode(&cal)
            m[binary.BigEndian.Uint64(k)] = cal
        }
        c.JSON(http.StatusOK, m)
        return nil
    })
}

func (this *RequestHandler) GetCalibration(c *gin.Context) {
    id, err := strconv.ParseUint(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.View(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("calibrations"))
        cb := b.Get(itob(id))
        if cb != nil {
            dec := codec.NewDecoderBytes(cb, this.H)
            var cal calibrationPair
            dec.Decode(&cal)
            c.JSON(http.StatusOK, cal)
        } else {
            c.Status(http.StatusNotFound)
        }
        return nil
    })
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
    var cb []byte
    enc := codec.NewEncoderBytes(&cb, this.H)
    enc.Encode(calibration)

    this.Db.Update(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("calibrations"))
        id, _ := b.NextSequence()
        err := b.Put(itob(id), cb)
        return err
    })

    c.Status(http.StatusCreated)
}

func (this *RequestHandler) DeleteCalibration (c *gin.Context) {
    id, err := strconv.ParseUint(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.Update(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("calibrations"))
        b.Delete(itob(id))
        c.Status(http.StatusNoContent)
        return nil
    })
}

func (this *RequestHandler) GetLinkages(c *gin.Context) {
    this.Db.View(func(tx *bbolt.Tx) error {
        m := make(map[uint64]linkage)
        b := tx.Bucket([]byte("linkages"))
        cur := b.Cursor()
        for k, v := cur.First(); k != nil; k, v = cur.Next() {
            dec := codec.NewDecoderBytes(v, this.H)
            var linkage linkage
            dec.Decode(&linkage)
            m[binary.BigEndian.Uint64(k)] = linkage
        }
        c.JSON(http.StatusOK, m)
        return nil
    })
}

func (this *RequestHandler) GetLinkage(c *gin.Context) {
    id, err := strconv.ParseUint(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.View(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("linkages"))
        cb := b.Get(itob(id))
        if cb != nil {
            dec := codec.NewDecoderBytes(cb, this.H)
            var linkage linkage
            dec.Decode(&linkage)
            c.JSON(http.StatusOK, linkage)
        } else {
            c.Status(http.StatusNotFound)
        }
        return nil
    })
}

func (this *RequestHandler) PutLinkage(c *gin.Context) {
    name := c.PostForm("name")
    file, _ := c.FormFile("leverage")
    f, _ := file.Open()
    linkage := newLinkage(name, f)
    var lb []byte
    enc := codec.NewEncoderBytes(&lb, this.H)
    enc.Encode(linkage)

    this.Db.Update(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("linkages"))
        id, _ := b.NextSequence()
        err := b.Put(itob(id), lb)
        return err
    })

    c.Status(http.StatusCreated)
}

func (this *RequestHandler) DeleteLinkage(c *gin.Context) {
    id, err := strconv.ParseUint(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.Update(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("linkages"))
        b.Delete(itob(id))
        c.Status(http.StatusNoContent)
        return nil
    })
}

func (this *RequestHandler) GetSessions(c *gin.Context) {
    this.Db.View(func(tx *bbolt.Tx) error {
        m := make(map[uint64]session)
        b := tx.Bucket([]byte("sessions"))
        cur := b.Cursor()
        for k, v := cur.First(); k != nil; k, v = cur.Next() {
            dec := codec.NewDecoderBytes(v, this.H)
            var session session
            dec.Decode(&session)
            m[binary.BigEndian.Uint64(k)] = session
        }
        c.JSON(http.StatusOK, m)
        return nil
    })
}

func (this *RequestHandler) GetSession(c *gin.Context) {
    id, err := strconv.ParseUint(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.View(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("sessions"))
        sb := b.Get(itob(id))
        if sb != nil {
            dec := codec.NewDecoderBytes(sb, this.H)
            var session session
            dec.Decode(&session)
            c.JSON(http.StatusOK, session)
        } else {
            c.Status(http.StatusNotFound)
        }
        return nil
    })
}

func (this *RequestHandler) PutSession(c *gin.Context) {
    var calibration calibrationPair
    calibrationId, err := strconv.ParseUint(c.PostForm("calibration"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.View(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("calibrations"))
        cb := b.Get(itob(calibrationId))
        dec := codec.NewDecoderBytes(cb, this.H)
        dec.Decode(&calibration)
        return nil
    })
    if calibration.Name == "" {
        c.AbortWithStatus(http.StatusUnprocessableEntity)
        return
    }

    var linkage linkage
    linkageId, err := strconv.ParseUint(c.PostForm("linkage"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.View(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("linkages"))
        cb := b.Get(itob(linkageId))
        dec := codec.NewDecoderBytes(cb, this.H)
        dec.Decode(&linkage)
        return nil
    })
    if linkage.Name == "" {
        c.AbortWithStatus(http.StatusUnprocessableEntity)
        return
    }

    file, _ := c.FormFile("recording")
    pd := prorcessRecording(file, linkage, calibration.Front, calibration.Rear)
    if pd == nil {
        c.AbortWithStatus(http.StatusUnprocessableEntity)
        return
    }
    fo, err := os.Create(path.Join("data", pd.Name))
    if err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
        return
    }
    defer fo.Close()
    enc := codec.NewEncoder(fo, this.H)
    enc.Encode(pd)

    var sb []byte
    enc = codec.NewEncoderBytes(&sb, this.H)
    enc.Encode(&session{
        Date: time.Now(),
        Path: pd.Name,
        Description: c.PostForm("description"),
    })

    this.Db.Update(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("sessions"))
        id, _ := b.NextSequence()
        err := b.Put(itob(id), sb)
        return err
    })

    c.Status(http.StatusCreated)
}

func (this *RequestHandler) DeleteSession(c *gin.Context) {
    id, err := strconv.ParseUint(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    this.Db.Update(func(tx *bbolt.Tx) error {
        b := tx.Bucket([]byte("sessions"))
        b.Delete(itob(id))
        c.Status(http.StatusNoContent)
        return nil
    })
}

func main() {
    var h codec.MsgpackHandle

    db, err := bbolt.Open("gosst.db", 0600, nil)
    if err != nil {
        return 
    }
    defer db.Close()
    db.Update(func(tx *bbolt.Tx) error {
        _, err := tx.CreateBucketIfNotExists([]byte("calibrations"))
        if err != nil {
            return fmt.Errorf("create bucket: %s", err)
        }
        _, err = tx.CreateBucketIfNotExists([]byte("linkages"))
        if err != nil {
            return fmt.Errorf("create bucket: %s", err)
        }
        _, err = tx.CreateBucketIfNotExists([]byte("sessions"))
        if err != nil {
            return fmt.Errorf("create bucket: %s", err)
        }
	    return nil
    })

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
    router.PUT("/session", (&RequestHandler{Db: db, H: &h}).PutSession)
    router.DELETE("/session/:id", (&RequestHandler{Db: db, H: &h}).DeleteSession)

    router.Run(":8080")
}
