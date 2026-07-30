"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import MarketReportCharts from "@/components/MarketReportCharts";
import { getMarketReport } from "@/lib/api";
import type { MarketReport } from "@/types";

export default function MarketReportPage() {
  const [report, setReport] = useState<MarketReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load(force: boolean) {
    setLoading(true);
    setError(null);
    getMarketReport(force)
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Quarterly Market Report
          </h1>
          {report && (
            <p className="text-slate-500 text-sm mt-1">
              Q{report.quarter} {report.year}
              {" · "}
              {report.cached ? "Cached, generated" : "Generated"}{" "}
              {new Date(report.generated_at).toLocaleString("en-IE")}
            </p>
          )}
        </div>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} />
          Regenerate
        </button>
      </div>

      {loading && !report && (
        <p className="text-sm text-slate-400">Generating market report...</p>
      )}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {report && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">
                Market Overview
              </h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                {report.market_overview}
              </p>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">
                Trend Analysis
              </h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                {report.trend_analysis}
              </p>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">
                Risk Assessment
              </h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                {report.risk_assessment}
              </p>
            </div>
          </div>

          <MarketReportCharts stats={report.quarterly_stats} />
        </>
      )}
    </div>
  );
}
