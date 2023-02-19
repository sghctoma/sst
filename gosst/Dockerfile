FROM golang:1.20-alpine AS build

WORKDIR /go/src/gosst

COPY go.mod ./
COPY go.sum ./
RUN go mod download

COPY . .
RUN go install -v ./cmd/...

FROM alpine:latest as gosst-http
WORKDIR /app
COPY --from=build /go/bin/gosst-http gosst-http
CMD ["./gosst-http", \
     "--database", "/data/gosst.db", \
     "--host", "0.0.0.0", \
     "--port", "8080"]

FROM alpine:latest as gosst-tcp
WORKDIR /app
COPY --from=build /go/bin/gosst-tcp gosst-tcp
CMD ["./gosst-tcp", \
     "--database", "/data/gosst.db", \
     "--host", "0.0.0.0", \
     "--port", "557"]