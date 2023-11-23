FORMATS_SOURCES := $(shell find formats -name "*.go")
INTERNAL_SOURCES := $(shell find internal -name "*.go")
CMD_SOURCES := $(shell find cmd -name "*.go")
LIB_SOURCES := $(shell find lib -name "*.go")

build: cmd

cmd: gosst-tcp gosst-http gosst-file

gosst-tcp: $(FORMATS_SOURCES) $(INTERNAL_SOURCES) $(CMD_SOURCES)
	go build -o dist/cmd/gosst-tcp cmd/gosst-tcp/gosst-tcp.go

gosst-http: $(FORMATS_SOURCES) $(INTERNAL_SOURCES) $(CMD_SOURCES)
	go build -o dist/cmd/gosst-http cmd/gosst-http/gosst-http.go

gosst-file: $(FORMATS_SOURCES) $(INTERNAL_SOURCES) $(CMD_SOURCES)
	go build -o dist/cmd/gosst-file cmd/gosst-file/gosst-file.go

clean:
	go clean
	rm -r dist
