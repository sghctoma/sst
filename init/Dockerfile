FROM alpine:latest as init

RUN apk add --no-cache openssl

WORKDIR /app

CMD if [ ! -f /data/private_key.pem ]; then \
        openssl genrsa -out /data/private_key.pem 2048; \
        openssl rsa -in /data/private_key.pem -outform PEM -pubout -out /data/public_key.pem; \
    fi
