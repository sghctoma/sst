package main

import (
	"database/sql"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/jessevdk/go-flags"
	"github.com/pebbe/zmq4"

	_ "modernc.org/sqlite"

	queries "gosst/internal/db"
)

type RequestHandler struct {
	Db     *sql.DB
	Socket *zmq4.Socket
}

func contains(list []string, e string) bool {
	for _, s := range list {
		if s == e {
			return true
		}
	}
	return false
}

func loadApiTokens(db *sql.DB) ([]string, error) {
	rows, err := db.Query(queries.Tokens)
	if err != nil {
		return nil, err
	}
	var tokens []string
	for rows.Next() {
		var t string
		if err := rows.Scan(&t); err == nil {
			tokens = append(tokens, t)
		}
	}
	return tokens, nil
}

func (this *RequestHandler) TokenAuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		tokens, err := loadApiTokens(this.Db)
		if err != nil {
			log.Println("Could not load API tokens.")
			c.AbortWithStatus(http.StatusUnauthorized)
			return
		}
		token := c.GetHeader("X-Token")
		if !contains(tokens, token) {
			c.AbortWithStatus(http.StatusUnauthorized)
			return
		}
		c.Next()
	}
}

func main() {
	var opts struct {
		DatabaseFile string `short:"d" long:"database" description:"SQLite3 database file path" required:"true"`
		Host         string `short:"h" long:"host" description:"Host to bind on" default:"127.0.0.1"`
		Port         string `short:"p" long:"port" description:"Port to bind on" default:"8080"`
		ZmqHost      string `short:"H" long:"zhost" description:"ZMQ server host" default:"127.0.0.1"`
		ZmqPort      string `short:"P" long:"zport" description:"ZMQ server port" default:"5555"`
	}
	_, err := flags.Parse(&opts)
	if err != nil {
		return
	}

	db, err := sql.Open("sqlite", opts.DatabaseFile)
	if err != nil {
		log.Fatal("Could not open database")
	}
	if _, err := db.Exec(queries.Schema); err != nil {
		log.Fatal("Could not create data tables")
	}

	soc, err := zmq4.NewSocket(zmq4.PUSH)
	defer soc.Close()
	if err != nil {
		log.Println("[WARN] could not create ZMQ socket (cache generation disabled)")
	} else {
		if err = soc.Connect("tcp://" + opts.ZmqHost + ":" + opts.ZmqPort); err != nil {
			log.Println("[WARN] could not connect to ZMQ server (cache generation disabled)")
			soc.Close()
			soc = nil
		}
	}

	rh := RequestHandler{Db: db, Socket: soc}
	//XXX gin.SetMode(gin.ReleaseMode)
	router := gin.Default()
	router.SetTrustedProxies(nil)

	router.GET("/calibrations", rh.GetCalibrations)
	router.GET("/calibration/:id", rh.GetCalibration)
	router.PUT("/calibration", rh.TokenAuthMiddleware(), rh.PutCalibration)
	router.DELETE("/calibration/:id", rh.TokenAuthMiddleware(), rh.DeleteCalibration)

	router.GET("/calibrationmethods", rh.GetCalibrationMethods)
	router.GET("/calibrationmethod/:id", rh.GetCalibrationMethod)
	router.PUT("/calibrationmethod", rh.TokenAuthMiddleware(), rh.PutCalibrationMethod)
	router.DELETE("/calibrationmethod/:id", rh.TokenAuthMiddleware(), rh.DeleteCalibrationMethod)

	router.GET("/linkages", rh.GetLinkages)
	router.GET("/linkage/:id", rh.GetLinkage)
	router.PUT("/linkage", rh.TokenAuthMiddleware(), rh.PutLinkage)
	router.DELETE("/linkage/:id", rh.TokenAuthMiddleware(), rh.DeleteLinkage)

	router.GET("/setups", rh.GetSetups)
	router.GET("/setup/:id", rh.GetSetup)
	router.PUT("/setup", rh.TokenAuthMiddleware(), rh.PutSetup)
	router.DELETE("/setup/:id", rh.TokenAuthMiddleware(), rh.DeleteSetup)

	router.PUT("/board", rh.TokenAuthMiddleware(), rh.PutBoard)
	router.DELETE("/board/:id", rh.TokenAuthMiddleware(), rh.DeleteBoard)

	router.GET("/sessions", rh.GetSessions)
	router.GET("/session/:id", rh.GetSession)
	router.GET("/sessiondata/:id", rh.GetSessionData)
	router.PUT("/session", rh.TokenAuthMiddleware(), rh.PutSession)
	router.DELETE("/session/:id", rh.TokenAuthMiddleware(), rh.DeleteSession)
	router.PATCH("/session/:id", rh.TokenAuthMiddleware(), rh.PatchSession)

	router.Run(opts.Host + ":" + opts.Port)
}
