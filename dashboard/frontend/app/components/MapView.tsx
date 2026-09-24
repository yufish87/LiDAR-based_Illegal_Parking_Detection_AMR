"use client";

import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import { ViolationEvent } from "@/app/types";

// Fix Leaflet default icon issue in Next.js
const createCustomIcon = (isSelected: boolean) =>
  L.divIcon({
    className: "",
    html: `
      <div style="
        width: 32px; height: 32px;
        background: ${isSelected ? "#3b82f6" : "#ef4444"};
        border: 3px solid ${isSelected ? "#93c5fd" : "#fca5a5"};
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        transition: all 0.2s ease;
      "></div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32],
  });

// Component to fly to selected event
function MapController({ selected }: { selected: ViolationEvent | null }) {
  const map = useMap();
  const prevId = useRef<string | null>(null);

  useEffect(() => {
    if (selected?.lat && selected?.lng && selected.id !== prevId.current) {
      prevId.current = selected.id;
      map.setView([selected.lat, selected.lng], 18, { animate: true });
    }
  }, [selected, map]);

  return null;
}

interface MapViewProps {
  events: ViolationEvent[];
  selectedId: string | null;
  onSelectEvent: (event: ViolationEvent) => void;
}

// Default center: NTUST campus
const DEFAULT_CENTER: [number, number] = [25.0136, 121.5396];

export default function MapView({ events, selectedId, onSelectEvent }: MapViewProps) {
  const eventsWithCoords = events.filter((e) => e.lat && e.lng);
  const selected = events.find((e) => e.id === selectedId) ?? null;

  // Determine initial center
  const initialCenter: [number, number] =
    eventsWithCoords.length > 0
      ? [eventsWithCoords[0].lat!, eventsWithCoords[0].lng!]
      : DEFAULT_CENTER;

  return (
    <MapContainer
      center={initialCenter}
      zoom={17}
      style={{ height: "100%", width: "100%" }}
      zoomControl={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <MapController selected={selected} />

      {eventsWithCoords.map((event) => {
        const isSelected = event.id === selectedId;
        return (
          <Marker
            key={event.id}
            position={[event.lat!, event.lng!]}
            icon={createCustomIcon(isSelected)}
            eventHandlers={{ click: () => onSelectEvent(event) }}
          >
            <Popup>
              <div style={{ minWidth: "200px", fontFamily: "system-ui, sans-serif" }}>
                <div style={{ fontSize: "13px", fontWeight: "700", color: "#e2e8f0", marginBottom: "8px", borderBottom: "1px solid #1e2d4a", paddingBottom: "6px" }}>
                  #{event.id}
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", lineHeight: "1.8" }}>
                  <div>時間：{event.timestamp}</div>
                  <div>區域：{event.zone}</div>
                  {event.address && <div>地址：{event.address}</div>}
                  {event.maps_url && (
                    <a href={event.maps_url} target="_blank" rel="noreferrer"
                      style={{ color: "#3b82f6", display: "block", marginTop: "6px" }}>
                      在 Google Maps 中開啟
                    </a>
                  )}
                </div>

              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
