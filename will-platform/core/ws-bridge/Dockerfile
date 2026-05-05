FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o ws-bridge .

FROM scratch
COPY --from=builder /src/ws-bridge /ws-bridge
EXPOSE 7000
ENTRYPOINT ["/ws-bridge"]
