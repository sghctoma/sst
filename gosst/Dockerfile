FROM golang:1.20 AS build

WORKDIR /go/src/gosst

COPY go.mod ./
COPY go.sum ./
RUN go mod download

COPY . .
RUN go install -v ./cmd/...

FROM debian:bookworm-slim as gosst-tcp
RUN apt-get update && apt-get -y install libzmq5
WORKDIR /app
COPY --from=build /go/bin/gosst-tcp gosst-tcp
CMD ["./gosst-tcp", \
     "--database", "/data/gosst.db", \
     "--host", "0.0.0.0", \
     "--port", "557", \
     "--cache", "cache:5555"]
