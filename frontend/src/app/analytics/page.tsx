import { getAnalyticsSummary } from "@/lib/api";
import StatCard from "@/components/StatCard";
import AnalyticsCharts from "@/components/AnalyticsCharts";

export default async function AnalyticsPage() {
  const summary = await getAnalyticsSummary();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <p className="text-slate-500 text-sm mt-1">
          Last recalculated:{" "}
          {new Date(summary.computed_at).toLocaleString("en-IE")}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Properties"
          value={summary.total_properties.toLocaleString("en-IE")}
        />
        <StatCard label="Average Score" value={`${summary.avg_score}%`} />
        <StatCard
          label="Retention Applications"
          value={summary.with_retention.toLocaleString("en-IE")}
        />
        <StatCard
          label="Derelict/Vacant"
          value={summary.with_derelict_or_vacant.toLocaleString("en-IE")}
        />
      </div>

      <AnalyticsCharts summary={summary} />
    </div>
  );
}
