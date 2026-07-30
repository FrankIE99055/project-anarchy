import { getAnalyticsSummary } from "@/lib/api";
import StatCard from "@/components/StatCard";
import PropertyMapClient from "@/components/PropertyMapClient";

export default async function DashboardPage() {
  const summary = await getAnalyticsSummary();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Overview</h1>
        <p className="text-slate-500 text-sm mt-1">
          Propensity to Sell &mdash; heatmap of properties across Ireland
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Properties"
          value={summary.total_properties.toLocaleString("en-IE")}
          accent="indigo"
        />
        <StatCard
          label="With GPS Location"
          value={summary.properties_with_location.toLocaleString("en-IE")}
          hint="Shown on the map"
          accent="slate"
        />
        <StatCard
          label="Average Score"
          value={`${summary.avg_score}%`}
          accent="orange"
        />
        <StatCard
          label="Score ≥ 50%"
          value={summary.score_bucket_50_60.toLocaleString("en-IE")}
          hint="Most interesting opportunities"
          accent="red"
        />
      </div>

      <div className="h-[560px]">
        <PropertyMapClient />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Retention Applications"
          value={summary.with_retention.toLocaleString("en-IE")}
        />
        <StatCard
          label="Derelict/Vacant"
          value={summary.with_derelict_or_vacant.toLocaleString("en-IE")}
        />
        <StatCard
          label="Daft Signals"
          value={summary.with_daft_signal.toLocaleString("en-IE")}
        />
        <StatCard
          label="Sales (PPR)"
          value={summary.total_sales_history.toLocaleString("en-IE")}
        />
      </div>
    </div>
  );
}
