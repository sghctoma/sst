package main

import (
	"database/sql"
	"encoding/base64"
	"io/ioutil"
	"log"
	"math"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/ugorji/go/codec"

	_ "modernc.org/sqlite"

	psst "gosst/internal/psst"
)

type session struct {
    Name        string    `codec:"," json:"name"`
    Description string    `codec:"," json:"description"`
    Calibration int64     `codec:"," json:"calibration"`
    Linkage     int64     `codec:"," json:"linkage"`
    Data        string    `codec:"," json:"data"`
}

type calibrationPair struct {
    Name  string      `codec:"," json:"name" binding:"required"`
    Front psst.Calibration `codec:"," json:"front" validate:"dive" binding:"required"`
    Rear  psst.Calibration `codec:"," json:"rear" validate:"dive" binding:"required"`
}

type RequestHandler struct {
    Db *sql.DB
    H codec.Handle
}

func (this *RequestHandler) GetCalibrations(c *gin.Context) {
    m := make(map[int64]calibrationPair)
    rows, err := this.Db.Query("SELECT ROWID, data FROM calibrations")
	if err != nil {
	    c.AbortWithStatus(http.StatusInternalServerError)
        return
	}
    for rows.Next() {
        var id int64
        var data []byte
        rows.Scan(&id, &data)

        dec := codec.NewDecoderBytes(data, this.H)
        var cal calibrationPair
        dec.Decode(&cal)
        m[id] = cal
    }
    c.JSON(http.StatusOK, m)
}

func (this *RequestHandler) GetCalibration(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    var data []byte
    err = this.Db.QueryRow("SELECT data FROM calibrations where ROWID = ?", id).Scan(&data)
    if err != nil {
        if err == sql.ErrNoRows {
            c.AbortWithStatus(http.StatusNotFound)
        } else {
            c.AbortWithStatus(http.StatusInternalServerError)
        }
        return
    }

    dec := codec.NewDecoderBytes(data, this.H)
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
    var data []byte
    enc := codec.NewEncoderBytes(&data, this.H)
    enc.Encode(calibration)

    if _, err := this.Db.Exec("INSERT INTO calibrations VALUES (?)", data); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusCreated)
    }
}

func (this *RequestHandler) DeleteCalibration (c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    if _, err := this.Db.Exec("DELETE FROM calibrations WHERE ROWID = ?", id); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusNoContent)
    }
}

func (this *RequestHandler) GetLinkages(c *gin.Context) {
    m := make(map[int64]psst.Linkage)
    rows, err := this.Db.Query("SELECT ROWID, data FROM linkages")
	if err != nil {
	    c.AbortWithStatus(http.StatusInternalServerError)
        return
	}
    for rows.Next() {
        var id int64
        var data []byte
        rows.Scan(&id, &data)

        dec := codec.NewDecoderBytes(data, this.H)
        var linkage psst.Linkage
        dec.Decode(&linkage)
        m[id] = linkage
    }
    c.JSON(http.StatusOK, m)
}

func (this *RequestHandler) GetLinkage(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    var data []byte
    err = this.Db.QueryRow("SELECT data FROM linkages where ROWID = ?", id).Scan(&data)
    if err != nil {
        if err == sql.ErrNoRows {
            c.AbortWithStatus(http.StatusNotFound)
        } else {
            c.AbortWithStatus(http.StatusInternalServerError)
        }
        return
    }

    dec := codec.NewDecoderBytes(data, this.H)
    var linkage psst.Linkage
    dec.Decode(&linkage)
    c.JSON(http.StatusOK, linkage)
}

func (this *RequestHandler) PutLinkage(c *gin.Context) {
    var linkage psst.Linkage
    if err := c.ShouldBindJSON(&linkage); err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    //linkage := newLinkage(linkage.Name, bytes.NewReader(raw))
    if linkage.Process() != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    var data []byte
    enc := codec.NewEncoderBytes(&data, this.H)
    enc.Encode(linkage)

    if _, err := this.Db.Exec("INSERT INTO linkages VALUES (?)", data); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusCreated)
    }
}

func (this *RequestHandler) DeleteLinkage(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    if _, err := this.Db.Exec("DELETE FROM linkages WHERE ROWID = ?", id); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusNoContent)
    }
}

func (this *RequestHandler) GetSessions(c *gin.Context) {
    m := make(map[int64]gin.H)
    rows, err := this.Db.Query("SELECT ROWID, name, description, date FROM sessions")
	if err != nil {
	    c.AbortWithStatus(http.StatusInternalServerError)
        return
	}
    for rows.Next() {
        var id int64
        var name, description string
        var date int64
        rows.Scan(&id, &name, &description, &date)

        m[id] = gin.H{"id": id, "name": name, "description": description, "date": time.Unix(date, 0)}
    }
    c.JSON(http.StatusOK, m)
}

func (this *RequestHandler) GetSession(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    var name, description string
    var date int64
    err = this.Db.QueryRow("SELECT name, description, date FROM sessions where ROWID = ?", id).Scan(&name, &description, &date)
    if err != nil {
        if err == sql.ErrNoRows {
            c.AbortWithStatus(http.StatusNotFound)
        } else {
            log.Println(err)
            c.AbortWithStatus(http.StatusInternalServerError)
        }
        return
    }

    c.JSON(http.StatusOK, gin.H{"name": name, "description": description, "date": time.Unix(date, 0)})
}

func (this *RequestHandler) GetSessionData(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    var name string
    var data []byte
    err = this.Db.QueryRow("SELECT name, data FROM sessions where ROWID = ?", id).Scan(&name, &data)
    if err != nil {
        if err == sql.ErrNoRows {
            c.AbortWithStatus(http.StatusNotFound)
        } else {
            c.AbortWithStatus(http.StatusInternalServerError)
        }
        return
    }

    c.Header("Content-Disposition", "attachment; filename=" + name)
    c.Data(http.StatusOK, "application/octet-stream", data)
}

func (this *RequestHandler) PutSession(c *gin.Context) {
    var session session
    if err := c.ShouldBindJSON(&session); err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    var calData []byte
    err := this.Db.QueryRow("SELECT data FROM calibrations where ROWID = ?", session.Calibration).Scan(&calData)
    if err != nil {
        if err == sql.ErrNoRows {
            c.AbortWithStatus(http.StatusNotFound)
        } else {
            c.AbortWithStatus(http.StatusInternalServerError)
        }
        return
    }

    cdec := codec.NewDecoderBytes(calData, this.H)
    var cpair calibrationPair
    cdec.Decode(&cpair)

    var lnkData []byte
    err = this.Db.QueryRow("SELECT data FROM linkages where ROWID = ?", session.Linkage).Scan(&lnkData)
    if err != nil {
        if err == sql.ErrNoRows {
            c.AbortWithStatus(http.StatusNotFound)
        } else {
            c.AbortWithStatus(http.StatusInternalServerError)
        }
        return
    }

    ldec := codec.NewDecoderBytes(lnkData, this.H)
    var linkage psst.Linkage
    ldec.Decode(&linkage)

    sst, err := base64.StdEncoding.DecodeString(session.Data)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    pd := psst.ProcessRecording(sst, session.Name, linkage, cpair.Front, cpair.Rear)
    if pd == nil {
        c.AbortWithStatus(http.StatusUnprocessableEntity)
        return
    }

    var data []byte
    enc := codec.NewEncoderBytes(&data, this.H)
    enc.Encode(pd)

    if _, err := this.Db.Exec("INSERT INTO sessions VALUES (?, ?, ?, ?)",
            session.Name, session.Description, pd.Timestamp, data); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusCreated)
    }
}

func (this *RequestHandler) DeleteSession(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    if _, err := this.Db.Exec("DELETE FROM sessions WHERE ROWID = ?", id); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusNoContent)
    }
}

func (this *RequestHandler) PatchSessionDescription(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    desc, err := ioutil.ReadAll(c.Request.Body)
    if err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }

    if _, err := this.Db.Exec("UPDATE sessions SET description = ? WHERE ROWID = ?", string(desc[:]), id); err != nil {
        c.AbortWithStatus(http.StatusInternalServerError)
    } else {
        c.Status(http.StatusNoContent)
    }
}

func main() {
    var h codec.MsgpackHandle

    db, err := sql.Open("sqlite", os.Args[1])
    if err != nil {
        log.Fatal("could not open database")
    }
    if _, err := db.Exec(`
            CREATE TABLE IF NOT EXISTS calibrations(data BLOB);
            CREATE TABLE IF NOT EXISTS linkages(data BLOB);
            CREATE TABLE IF NOT EXISTS sessions(name TEXT, description TEXT, date INTEGER, data BLOB);`); err != nil {
        log.Fatal("could not create data tables")
    }

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
    router.PATCH("/session/:id/description", (&RequestHandler{Db: db, H: &h}).PatchSessionDescription)

    router.Run("127.0.0.1:8080")
}
