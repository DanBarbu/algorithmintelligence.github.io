"""
WILL Platform — Sprint 0 (S0-04)
Simulated GPS plugin: orbits Bucharest at 1 Hz on telemetry/gps/sim01.
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

EMQX_HOST: str = os.getenv("EMQX_HOST", "localhost")
EMQX_PORT: int = int(os.getenv("EMQX_PORT", "1883"))
TOPIC: str = os.getenv("TOPIC", "telemetry/gps/sim01")
HZ: float = float(os.getenv("HZ", "1"))

# Orbit centre: Bucharest
CENTER_LAT: float = 44.4268
CENTER_LON: float = 26.1025
RADIUS_DEG: float = 0.05
ALTITUDE_M: float = 1500.0
SPEED_MS: float = 80.0
TRACK_ID: str = "SIM-GPS-01"


def build_payload(angle_deg: float) -> str:
    angle_rad = math.radians(angle_deg)
    lat = CENTER_LAT + RADIUS_DEG * math.cos(angle_rad)
    lon = CENTER_LON + RADIUS_DEG * math.sin(angle_rad)
    heading = (angle_deg + 90.0) % 360.0
    return json.dumps(
        {
            "track_id": TRACK_ID,
            "lat": round(lat, 6),
            "lng": round(lon, 6),
            "altitude_m": ALTITUDE_M,
            "speed_ms": SPEED_MS,
            "heading_deg": round(heading, 1),
            "classification": "UNCLASSIFIED",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


def on_connect(client: mqtt.Client, userdata: None, flags: dict[str, int], rc: int) -> None:
    if rc == 0:
        print(f"[gps-sim] Connected to EMQX {EMQX_HOST}:{EMQX_PORT}", flush=True)
    else:
        print(f"[gps-sim] Connection failed rc={rc}", flush=True)


def main() -> None:
    client = mqtt.Client(client_id="will-gps-sim")
    client.on_connect = on_connect
    client.connect(EMQX_HOST, EMQX_PORT, keepalive=60)
    client.loop_start()

    interval = 1.0 / HZ
    angle = 0.0
    angular_step = 360.0 * interval / 60.0  # full orbit in ~60 s

    print(f"[gps-sim] Publishing to {TOPIC} at {HZ} Hz", flush=True)
    while True:
        payload = build_payload(angle)
        client.publish(TOPIC, payload, qos=0)
        angle = (angle + angular_step) % 360.0
        time.sleep(interval)


if __name__ == "__main__":
    main()
