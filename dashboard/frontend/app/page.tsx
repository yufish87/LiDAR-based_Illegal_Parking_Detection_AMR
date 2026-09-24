import { ViolationEvent } from "@/app/types";
import DashboardClient from "@/app/components/DashboardClient";

const API_URL = process.env.NEXT_PUBLIC_GAS_API_URL || "";


function parseCoords(mapsUrl: string): { lat?: number; lng?: number } {
  if (!mapsUrl) return {};
  const match = mapsUrl.match(/query=([-\d.]+),([-\d.]+)/);
  if (match) {
    return { lat: parseFloat(match[1]), lng: parseFloat(match[2]) };
  }
  return {};
}

async function getEvents(): Promise<ViolationEvent[]> {
  try {
    const res = await fetch(`${API_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return [];
    const raw: ViolationEvent[] = await res.json();
    // Add parsed coordinates & reverse so newest is first
    return raw
      .map((e) => ({ ...e, ...parseCoords(e.maps_url) }))
      .reverse();
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const events = await getEvents();
  const lastUpdated = new Date().toLocaleString("zh-TW", { timeZone: "Asia/Taipei" });

  return <DashboardClient initialEvents={events} lastUpdated={lastUpdated} />;
}
