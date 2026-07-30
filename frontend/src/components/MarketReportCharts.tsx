"use client";

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { QuarterlyStat } from "@/types";

function quarterLabel(s: QuarterlyStat) {
  return `Q${s.quarter} ${s.year}`;
}

export default function MarketReportCharts({ stats }: { stats: QuarterlyStat[] }) {
  const data = stats.map((s) => ({
    label: quarterLabel(s),
    avg_sold_price: s.avg_sold_price,
    median_sold_price: s.median_sold_price,
    sold_count: s.sold_count,
  }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">
          Avg / Median Sold Price by Quarter (Daft.ie)
        </h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="label" fontSize={11} interval={1} />
            <YAxis
              tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`}
              fontSize={12}
              width={55}
            />
            <Tooltip formatter={(v) => `€${Number(v).toLocaleString("en-IE")}`} />
            <Line
              type="monotone"
              dataKey="avg_sold_price"
              name="Average"
              stroke="#4f46e5"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="median_sold_price"
              name="Median"
              stroke="#f97316"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">
          Sold Volume by Quarter (Daft.ie)
        </h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="label" fontSize={11} interval={1} />
            <YAxis fontSize={12} width={45} />
            <Tooltip />
            <Bar dataKey="sold_count" fill="#4f46e5" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
