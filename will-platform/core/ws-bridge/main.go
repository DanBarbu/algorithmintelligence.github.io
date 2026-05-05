// WILL Platform — Sprint 0 (S0-05)
// WebSocket bridge: subscribes EMQX telemetry/# → broadcasts JSON on /tracks.
package main

import (
	"log"
	"net/http"
	"os"
	"sync"

	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/gorilla/websocket"
)

var (
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}
	clients   = make(map[*websocket.Conn]struct{})
	clientsMu sync.RWMutex
)

func broadcast(msg []byte) {
	clientsMu.RLock()
	defer clientsMu.RUnlock()
	for c := range clients {
		if err := c.WriteMessage(websocket.TextMessage, msg); err != nil {
			log.Printf("ws write error: %v", err)
		}
	}
}

func wsHandler(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("ws upgrade: %v", err)
		return
	}
	clientsMu.Lock()
	clients[conn] = struct{}{}
	clientsMu.Unlock()

	defer func() {
		clientsMu.Lock()
		delete(clients, conn)
		clientsMu.Unlock()
		conn.Close()
	}()

	// block until client disconnects
	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
}

func healthz(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}

func mqttMessageHandler(_ mqtt.Client, msg mqtt.Message) {
	broadcast(msg.Payload())
}

func main() {
	emqxURL := envOr("EMQX_URL", "tcp://localhost:1883")
	listenAddr := envOr("LISTEN_ADDR", ":7000")

	opts := mqtt.NewClientOptions().
		AddBroker(emqxURL).
		SetClientID("will-ws-bridge").
		SetAutoReconnect(true).
		SetOnConnectHandler(func(c mqtt.Client) {
			log.Printf("MQTT connected to %s", emqxURL)
			if tok := c.Subscribe("telemetry/#", 0, mqttMessageHandler); tok.Wait() && tok.Error() != nil {
				log.Fatalf("MQTT subscribe: %v", tok.Error())
			}
			log.Println("Subscribed to telemetry/#")
		})

	client := mqtt.NewClient(opts)
	if tok := client.Connect(); tok.Wait() && tok.Error() != nil {
		log.Fatalf("MQTT connect: %v", tok.Error())
	}

	http.HandleFunc("/tracks", wsHandler)
	http.HandleFunc("/healthz", healthz)

	log.Printf("Listening on %s", listenAddr)
	if err := http.ListenAndServe(listenAddr, nil); err != nil {
		log.Fatalf("http: %v", err)
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
