FROM golang:alpine AS builder

WORKDIR /app
COPY npu-device-plugin .

RUN go install

FROM alpine:latest

COPY --from=builder /go/bin/device-plugin /usr/local/bin/device-plugin

ENTRYPOINT ["/usr/local/bin/device-plugin"]
