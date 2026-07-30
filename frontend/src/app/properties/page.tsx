"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import SearchBar from "@/components/SearchBar";
import ScoreBadge from "@/components/ScoreBadge";
import { searchProperties } from "@/lib/api";
import type { PropertySearchResponse } from "@/types";

const PAGE_SIZE = 25;

export default function PropertiesPage() {
  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PropertySearchResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timeout = setTimeout(() => {
      searchProperties({ q: query, minScore, page, pageSize: PAGE_SIZE })
        .then((res) => {
          if (!cancelled) setData(res);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 300); // debounce vyhledávání

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [query, minScore, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Properties</h1>
        <p className="text-slate-500 text-sm mt-1">
          Search and filter across the entire database
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1">
          <SearchBar
            value={query}
            onChange={(v) => {
              setQuery(v);
              setPage(1);
            }}
          />
        </div>
        <select
          value={minScore}
          onChange={(e) => {
            setMinScore(Number(e.target.value));
            setPage(1);
          }}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value={0}>All scores</option>
          <option value={30}>Score ≥ 30%</option>
          <option value={50}>Score ≥ 50%</option>
          <option value={70}>Score ≥ 70%</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Address</th>
              <th className="text-left px-4 py-3 font-medium">Eircode</th>
              <th className="text-left px-4 py-3 font-medium">Score</th>
              <th className="text-left px-4 py-3 font-medium">Key Signals</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && data?.results.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                  No results found.
                </td>
              </tr>
            )}
            {!loading &&
              data?.results.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link
                      href={`/properties/${p.id}`}
                      className="text-indigo-600 hover:underline font-medium"
                    >
                      {p.address}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{p.eircode ?? "—"}</td>
                  <td className="px-4 py-3">
                    <ScoreBadge score={p.propensity_score} size="sm" />
                  </td>
                  <td className="px-4 py-3 text-slate-500 max-w-md truncate">
                    {p.key_drivers?.join(", ") || "—"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>

        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-sm text-slate-500">
          <span>
            {data ? `${data.total.toLocaleString("en-IE")} results` : ""}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-md border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
            >
              <ChevronLeft size={16} />
            </button>
            <span>
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-md border border-slate-300 disabled:opacity-40 hover:bg-slate-50"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
