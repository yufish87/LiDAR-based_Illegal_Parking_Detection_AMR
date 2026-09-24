"use client";

import { useState } from "react";
import { ViolationEvent } from "@/app/types";

const GAS_URL = process.env.NEXT_PUBLIC_GAS_API_URL || "";

interface EventCardProps {
  event: ViolationEvent;
  isSelected: boolean;
  onClick: () => void;
  onStatusUpdate: (id: string, newStatus: string) => void;
}

function StatusBadge({ status }: { status: string }) {
  if (!status || status === "") {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
        style={{
          background: "rgba(245,158,11,0.15)",
          color: "#f59e0b",
          border: "1px solid rgba(245,158,11,0.3)",
        }}
      >
        待審核
      </span>
    );
  }
  if (status.includes("確認") || status === "已核准") {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
        style={{
          background: "rgba(34,197,94,0.15)",
          color: "#22c55e",
          border: "1px solid rgba(34,197,94,0.3)",
        }}
      >
        {status}
      </span>
    );
  }
  if (status.includes("誤判") || status === "已駁回") {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
        style={{
          background: "rgba(239,68,68,0.15)",
          color: "#ef4444",
          border: "1px solid rgba(239,68,68,0.3)",
        }}
      >
        {status}
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
      style={{
        background: "rgba(100,116,139,0.2)",
        color: "#94a3b8",
        border: "1px solid rgba(100,116,139,0.3)",
      }}
    >
      {status}
    </span>
  );
}

export default function EventCard({
  event,
  isSelected,
  onClick,
  onStatusUpdate,
}: EventCardProps) {
  const [loading, setLoading] = useState<"confirm" | "reject" | null>(null);
  const needsAudit = !event.status || event.status === "";

  const handleAudit = async (
    e: React.MouseEvent,
    newStatus: string,
    type: "confirm" | "reject"
  ) => {
    e.stopPropagation(); // 避免觸發卡片 onClick
    setLoading(type);
    try {
      await fetch(GAS_URL, {
        method: "POST",
        body: JSON.stringify({
          action: "update_status",
          event_id: event.id,
          status: newStatus,
        }),
      });
      onStatusUpdate(event.id, newStatus);
    } catch (err) {
      console.error("審核更新失敗:", err);
    } finally {
      setLoading(null);
    }
  };

  const getThumbnailUrl = (url: string) => {
    if (!url) return "";
    const match = url.match(/id=([^&]+)/);
    if (match && match[1]) {
      return `https://drive.google.com/thumbnail?id=${match[1]}&sz=w800`;
    }
    return url;
  };

  const hasValidImage = event.image_url && event.image_url.startsWith("http");

  return (
    <div
      onClick={onClick}
      className={`rounded-xl overflow-hidden cursor-pointer transition-all duration-200 ${
        isSelected ? "card-selected" : ""
      }`}
      style={{
        background: isSelected ? "var(--bg-card-hover)" : "var(--bg-card)",
        border: `1px solid ${
          isSelected ? "var(--accent-blue)" : "var(--border-color)"
        }`,
        transform: isSelected ? "scale(1.01)" : "scale(1)",
      }}
    >
      {/* Photo */}
      {hasValidImage ? (
        <div className="relative w-full bg-black/40" style={{ height: "220px" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={getThumbnailUrl(event.image_url)}
            alt={`違停現場 ${event.id}`}
            className="w-full h-full object-contain p-1"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "linear-gradient(to top, rgba(10,14,26,0.6) 0%, transparent 40%)",
            }}
          />
          <div
            className="absolute top-2 left-2 px-2 py-1 rounded text-xs font-mono font-bold"
            style={{
              background: "rgba(10,14,26,0.8)",
              color: "var(--accent-cyan)",
              border: "1px solid rgba(6,182,212,0.3)",
            }}
          >
            #{event.id}
          </div>
          <div className="absolute top-2 right-2">
            <StatusBadge status={event.status} />
          </div>
        </div>
      ) : (
        <div
          className="relative w-full flex items-center justify-center text-xs font-medium"
          style={{ height: "90px", background: "rgba(30,45,74,0.5)", color: "var(--text-muted)" }}
        >
          無現場影像
          <div
            className="absolute top-2 left-2 px-2 py-1 rounded text-xs font-mono font-bold"
            style={{
              background: "rgba(10,14,26,0.8)",
              color: "var(--accent-cyan)",
              border: "1px solid rgba(6,182,212,0.3)",
            }}
          >
            #{event.id}
          </div>
          <div className="absolute top-2 right-2">
            <StatusBadge status={event.status} />
          </div>
        </div>
      )}

      {/* Info */}
      <div className="p-3 space-y-2">
        <div
          className="flex items-center justify-between text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          <span style={{ color: "var(--text-muted)" }}>時間</span>
          <span>{event.timestamp}</span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span style={{ color: "var(--text-muted)" }}>區域</span>
          <span
            className="font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            {event.zone || "未知區域"}
          </span>
        </div>

        {event.address && (
          <div className="flex items-start justify-between text-xs gap-2">
            <span className="shrink-0" style={{ color: "var(--text-muted)" }}>
              地址
            </span>
            <span
              className="text-right leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {event.address}
            </span>
          </div>
        )}

        {event.notes && (
          <div
            className="text-xs px-2 py-1 rounded"
            style={{
              background: "rgba(30,45,74,0.5)",
              color: "var(--text-muted)",
            }}
          >
            {event.notes}
          </div>
        )}

        {/* Audit buttons */}
        {needsAudit ? (
          <div className="flex gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
            <button
              disabled={loading !== null}
              onClick={(e) => handleAudit(e, "已確認", "confirm")}
              className="flex-1 flex items-center justify-center py-1.5 rounded-lg text-xs font-semibold transition-all duration-150"
              style={{
                background:
                  loading === "confirm"
                    ? "rgba(34,197,94,0.1)"
                    : "rgba(34,197,94,0.15)",
                border: "1px solid rgba(34,197,94,0.4)",
                color: "#22c55e",
                cursor: loading !== null ? "not-allowed" : "pointer",
                opacity: loading !== null && loading !== "confirm" ? 0.4 : 1,
              }}
            >
              {loading === "confirm" ? "處理中..." : "確認違停"}
            </button>
            <button
              disabled={loading !== null}
              onClick={(e) => handleAudit(e, "誤判", "reject")}
              className="flex-1 flex items-center justify-center py-1.5 rounded-lg text-xs font-semibold transition-all duration-150"
              style={{
                background:
                  loading === "reject"
                    ? "rgba(239,68,68,0.1)"
                    : "rgba(239,68,68,0.15)",
                border: "1px solid rgba(239,68,68,0.4)",
                color: "#ef4444",
                cursor: loading !== null ? "not-allowed" : "pointer",
                opacity: loading !== null && loading !== "reject" ? 0.4 : 1,
              }}
            >
              {loading === "reject" ? "處理中..." : "誤判剔除"}
            </button>
          </div>
        ) : (
          <div className="pt-1">
            <StatusBadge status={event.status} />
          </div>
        )}
      </div>
    </div>
  );
}
