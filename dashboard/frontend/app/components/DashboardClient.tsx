"use client";

import { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { ViolationEvent } from "@/app/types";
import EventCard from "./EventCard";

// Dynamic import for Leaflet (SSR disabled)
const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => (
    <div
      className="flex items-center justify-center h-full"
      style={{ background: "var(--bg-primary)", color: "var(--text-muted)" }}
    >
      <div className="flex flex-col items-center gap-3">
        <span className="text-sm">載入地圖中...</span>
      </div>
    </div>
  ),
});

interface DashboardClientProps {
  initialEvents: ViolationEvent[];
  lastUpdated: string;
}

const API_URL = process.env.NEXT_PUBLIC_GAS_API_URL || "";

function parseCoords(mapsUrl: string): { lat?: number; lng?: number } {
  if (!mapsUrl) return {};
  const match = mapsUrl.match(/query=([-\d.]+),([-\d.]+)/);
  if (match) {
    return { lat: parseFloat(match[1]), lng: parseFloat(match[2]) };
  }
  return {};
}

export default function DashboardClient({
  initialEvents,
  lastUpdated: initialLastUpdated,
}: DashboardClientProps) {
  const [events, setEvents] = useState<ViolationEvent[]>(initialEvents);
  const [selectedId, setSelectedId] = useState<string | null>(
    initialEvents.length > 0 ? initialEvents[0].id : null
  );
  const [lastUpdated, setLastUpdated] = useState(initialLastUpdated);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isOnline, setIsOnline] = useState(true);

  const handleStatusUpdate = useCallback((id: string, newStatus: string) => {
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, status: newStatus } : e))
    );
  }, []);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch(`${API_URL}?t=${Date.now()}`, { cache: "no-store" });
      const raw: ViolationEvent[] = await res.json();
      const processed = raw.map((e) => ({ ...e, ...parseCoords(e.maps_url) }));
      setEvents(processed.reverse());
      setLastUpdated(new Date().toLocaleString("zh-TW", { timeZone: "Asia/Taipei" }));
      setIsOnline(true);
    } catch {
      setIsOnline(false);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  const handleSelectEvent = useCallback((event: ViolationEvent) => {
    setSelectedId(event.id);
  }, []);

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--bg-primary)" }}>
      {/* Header */}
      <header
        className="shrink-0 flex items-center justify-between px-5 py-3"
        style={{
          background: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border-color)",
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="px-2.5 py-1 rounded text-xs font-bold tracking-wider"
            style={{
              background: "linear-gradient(135deg, #1d4ed8, #0891b2)",
              color: "white",
            }}
          >
            AMR
          </div>
          <div>
            <h1
              className="text-base font-bold tracking-wide"
              style={{ color: "var(--text-primary)" }}
            >
              校園違停監控中心
            </h1>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              科技執法系統 · LiDAR PointPillars
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Event count */}
          <div
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg"
            style={{
              background: "rgba(59,130,246,0.1)",
              border: "1px solid rgba(59,130,246,0.2)",
            }}
          >
            <span
              className="text-sm font-medium"
              style={{ color: "var(--accent-blue)" }}
            >
              {events.length} 筆事件
            </span>
          </div>

          {/* Online indicator */}
          <div
            className="flex items-center gap-1.5"
            style={{
              color: isOnline ? "var(--accent-green)" : "var(--accent-red)",
            }}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{
                background: isOnline ? "var(--accent-green)" : "var(--accent-red)",
              }}
            />
            <span className="text-xs hidden sm:block">
              {isOnline ? "連線中" : "離線"}
            </span>
          </div>

          {/* Last updated */}
          <span
            className="text-xs hidden md:block"
            style={{ color: "var(--text-muted)" }}
          >
            更新於 {lastUpdated}
          </span>

          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200"
            style={{
              background: "rgba(59,130,246,0.15)",
              border: "1px solid rgba(59,130,246,0.3)",
              color: "var(--accent-blue)",
              cursor: isRefreshing ? "not-allowed" : "pointer",
              opacity: isRefreshing ? 0.6 : 1,
            }}
          >
            {isRefreshing ? "更新中..." : "重新整理"}
          </button>
        </div>
      </header>

      {/* Main content: split panel */}
      <div className="flex flex-1 overflow-hidden flex-col lg:flex-row">
        {/* Left panel: Event list */}
        <div
          className="lg:w-[420px] w-full lg:h-full h-1/2 flex flex-col"
          style={{ borderRight: "1px solid var(--border-color)" }}
        >
          {/* Panel header */}
          <div
            className="px-4 py-2.5 flex items-center justify-between shrink-0"
            style={{
              borderBottom: "1px solid var(--border-color)",
              background: "rgba(15,22,41,0.5)",
            }}
          >
            <span
              className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: "var(--text-muted)" }}
            >
              違停事件列表
            </span>
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{
                background: "rgba(239,68,68,0.15)",
                color: "#ef4444",
                border: "1px solid rgba(239,68,68,0.2)",
              }}
            >
              {events.filter((e) => !e.status || e.status === "").length} 待審
            </span>
          </div>

          {/* Scrollable list */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {events.length === 0 ? (
              <div
                className="flex flex-col items-center justify-center h-full gap-3"
                style={{ color: "var(--text-muted)" }}
              >
                <p className="text-sm">目前無違停紀錄</p>
              </div>
            ) : (
              events.map((event) => (
                <EventCard
                  key={event.id}
                  event={event}
                  isSelected={event.id === selectedId}
                  onClick={() => handleSelectEvent(event)}
                  onStatusUpdate={handleStatusUpdate}
                />
              ))
            )}
          </div>
        </div>

        {/* Right panel: Map */}
        <div className="flex-1 lg:h-full h-1/2 relative">
          <MapView
            events={events}
            selectedId={selectedId}
            onSelectEvent={handleSelectEvent}
          />

          {/* Map overlay: info */}
          <div
            className="absolute bottom-4 left-4 z-[1000] px-3 py-2 rounded-lg text-xs"
            style={{
              background: "rgba(10,14,26,0.85)",
              border: "1px solid var(--border-color)",
              color: "var(--text-muted)",
              backdropFilter: "blur(8px)",
            }}
          >
            點擊事件卡片可定位至該座標
          </div>
        </div>
      </div>
    </div>
  );
}
