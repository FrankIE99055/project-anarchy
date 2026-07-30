"use client";

import dynamic from "next/dynamic";

// Leaflet potřebuje window/document - musí to být čistě client-side,
// bez server-side renderování.
const PropertyMap = dynamic(() => import("./PropertyMap"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full rounded-xl border border-slate-200 bg-white flex items-center justify-center text-sm text-slate-400">
      Loading map...
    </div>
  ),
});

export default function PropertyMapClient({ minScore = 0 }: { minScore?: number }) {
  return <PropertyMap minScore={minScore} />;
}
