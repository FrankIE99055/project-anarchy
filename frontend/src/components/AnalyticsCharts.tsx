"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import type { AnalyticsSummary } from "@/types";

const SCORE_COLORS = [
  "#94a3b8",
  "#a3a3a3",
  "#fbbf24",
  "#f59e0b",
  "#f97316",
  "#ea580c",
  "#dc2626",
  "#b91c1c",
  "#991b1b",
  "#7f1d1d",
];

export default function AnalyticsCharts({ summary }: { summary: AnalyticsSummary }) {
  const distribution = [
    { range: "0-10", count: summary.score_bucket_0_10 },
    { range: "10-20", count: summary.score_bucket_10_20 },
    { range: "20-30", count: summary.score_bucket_20_30 },
    { range: "30-40", count: summary.score_bucket_30_40 },
    { range: "40-50", count: summary.score_bucket_40_50 },
    { range: "50-60", count: summary.score_bucket_50_60 },
    { range: "60-70", count: summary.score_bucket_60_70 },
    { range: "70-80", count: summary.score_bucket_70_80 },
    { range: "80-90", count: summary.score_bucket_80_90 },
    { range: "90-100", count: summary.score_bucket_90_100 },
  ];

  const sourceCounts = [
    { name: "PPR Sales", value: summary.total_sales_history },
    { name: "Planning Permissions", value: summary.total_planning_permissions },
    { name: "Daft Listings", value: summary.total_daft_listings },
    { name: "Derelict/Vacant", value: summary.total_derelict_sites },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">
          Propensity Score Distribution
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={distribution}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="range" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {distribution.map((_, i) => (
                <Cell key={i} fill={SCORE_COLORS[i]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">
          Data Source Sizes
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={sourceCounts}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={(entry) => entry.name}
            >
              {sourceCounts.map((_, i) => (
                <Cell key={i} fill={["#6366f1", "#0ea5e9", "#f59e0b", "#dc2626"][i]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
