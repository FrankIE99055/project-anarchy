"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import Link from "next/link";
import type { PropertyMapPoint } from "@/types";
import { scoreColor } from "./ScoreBadge";
import { getPropertiesForMap } from "@/lib/api";

const DUBLIN_CENTER: [number, number] = [53.35, -6.26];

export default function PropertyMap({ minScore = 0 }: { minScore?: number }) {
  const [points, setPoints] = useState<PropertyMapPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getPropertiesForMap(1500, minScore)
      .then((data) => {
        if (!cancelled) setPoints(data);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [minScore]);

  return (
    <div className="relative h-full w-full rounded-xl overflow-hidden border border-slate-200">
      {loading && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-white/70 text-sm text-slate-500">
          Loading map...
        </div>
      )}
      <MapContainer
        center={DUBLIN_CENTER}
        zoom={9}
        className="h-full w-full"
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {points.map((p) => (
          <CircleMarker
            key={p.id}
            center={[p.latitude, p.longitude]}
            radius={6}
            pathOptions={{
              color: scoreColor(p.propensity_score),
              fillColor: scoreColor(p.propensity_score),
              fillOpacity: 0.75,
              weight: 1,
            }}
          >
            <Popup>
              <div className="text-sm">
                <p className="font-semibold">{p.address}</p>
                {p.eircode && <p className="text-slate-500">{p.eircode}</p>}
                <p className="mt-1">
                  Score: <strong>{p.propensity_score.toFixed(0)}%</strong>
                </p>
                <Link
                  href={`/properties/${p.id}`}
                  className="text-indigo-600 hover:underline text-xs"
                >
                  View details →
                </Link>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
