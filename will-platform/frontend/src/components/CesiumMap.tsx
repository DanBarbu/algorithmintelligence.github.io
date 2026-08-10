import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../i18n/config";
import * as Cesium from "cesium";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:7000/tracks";
const CESIUM_TOKEN = import.meta.env.VITE_CESIUM_TOKEN ?? "";

interface TrackMsg {
  track_id: string;
  lat: number;
  lng: number;
  altitude_m: number;
  heading_deg: number;
  classification: string;
}

export default function CesiumMap(): JSX.Element {
  const { t } = useTranslation();
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const entityRef = useRef<Cesium.Entity | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (CESIUM_TOKEN) Cesium.Ion.defaultAccessToken = CESIUM_TOKEN;
    const viewer = new Cesium.Viewer(containerRef.current as Element, {
      terrainProvider: new Cesium.EllipsoidTerrainProvider(),
      baseLayerPicker: false,
      navigationHelpButton: false,
      sceneModePicker: false,
      geocoder: false,
      homeButton: false,
      timeline: false,
      animation: false,
      fullscreenButton: false,
    });
    viewerRef.current = viewer;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(26.1025, 44.4268, 80000),
    });

    // APP-6D friendly air: blue rectangle
    const entity = viewer.entities.add({
      name: "SIM-GPS-01",
      position: Cesium.Cartesian3.fromDegrees(26.1025, 44.4268, 1500),
      rectangle: {
        coordinates: Cesium.Rectangle.fromDegrees(-0.002, -0.001, 0.002, 0.001),
        material: Cesium.Color.DODGERBLUE.withAlpha(0.85),
        height: 1500,
        outline: true,
        outlineColor: Cesium.Color.WHITE,
      },
      label: {
        text: "SIM-GPS-01",
        font: "12px sans-serif",
        fillColor: Cesium.Color.WHITE,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -20),
      },
    });
    entityRef.current = entity;

    return () => { viewer.destroy(); };
  }, []);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev: MessageEvent<string>) => {
      try {
        const msg = JSON.parse(ev.data) as TrackMsg;
        if (entityRef.current) {
          (entityRef.current as Cesium.Entity).position =
            new Cesium.ConstantPositionProperty(
              Cesium.Cartesian3.fromDegrees(msg.lng, msg.lat, msg.altitude_m)
            );
        }
      } catch {
        // malformed payload — ignore
      }
    };
    return () => ws.close();
  }, []);

  function toggleLang(): void {
    i18n.changeLanguage(i18n.language === "en" ? "ro" : "en");
  }

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {/* Classification banner — top */}
      <div style={styles.banner}>{t("map.classification")}</div>

      {/* Status bar — top right */}
      <div style={styles.status}>
        <span style={{ color: connected ? "#3fb950" : "#f85149" }}>
          {connected ? t("map.connected") : t("map.connecting")}
        </span>
        <button onClick={toggleLang} style={styles.langBtn} type="button">
          {t("lang.toggle")}
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  banner: {
    position: "absolute", top: 0, left: 0, right: 0,
    background: "#238636", color: "#fff", textAlign: "center",
    fontSize: 12, fontWeight: 700, letterSpacing: 2,
    padding: "3px 0", pointerEvents: "none", zIndex: 10,
  },
  status: {
    position: "absolute", top: 24, right: 12,
    display: "flex", alignItems: "center", gap: 10, zIndex: 10,
  },
  langBtn: {
    background: "#21262d", color: "#58a6ff", border: "1px solid #30363d",
    borderRadius: 4, padding: "4px 10px", cursor: "pointer", fontSize: 13,
  },
};
