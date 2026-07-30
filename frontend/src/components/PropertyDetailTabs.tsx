"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  History as HistoryIcon,
  Info,
  ExternalLink,
  Search,
  Brain,
  FileDown,
  LineChart as LineChartIcon,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import ScoreBadge from "@/components/ScoreBadge";
import {
  analyzeTimeline,
  getPropertyCharts,
  getPropertyExplanation,
  getPropertyHistory,
  getReportUrl,
  researchProperty,
} from "@/lib/api";
import type {
  PropertyCharts,
  PropertyExplanation,
  PropertyHistory,
  PropertyResearchResult,
  PropertySummary,
  TimelineAnalysisResult,
} from "@/types";

type Tab = "overview" | "history" | "ai" | "charts";

function formatDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-IE");
}

function formatMoney(v: number | null) {
  if (v === null || v === undefined) return "—";
  return `€${v.toLocaleString("en-IE")}`;
}

export default function PropertyDetailTabs({
  property,
}: {
  property: PropertySummary & { property_id: string };
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const [history, setHistory] = useState<PropertyHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [explanation, setExplanation] = useState<PropertyExplanation | null>(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [research, setResearch] = useState<PropertyResearchResult | null>(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineAnalysisResult | null>(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [charts, setCharts] = useState<PropertyCharts | null>(null);
  const [chartsLoading, setChartsLoading] = useState(false);
  const [chartsError, setChartsError] = useState<string | null>(null);

  function runResearch(force: boolean) {
    setResearchLoading(true);
    setResearchError(null);
    researchProperty(property.property_id, force)
      .then(setResearch)
      .catch((e) => setResearchError(e.message))
      .finally(() => setResearchLoading(false));
  }

  function runTimelineAnalysis() {
    setTimelineLoading(true);
    setTimelineError(null);
    analyzeTimeline(property.property_id)
      .then(setTimeline)
      .catch((e) => setTimelineError(e.message))
      .finally(() => setTimelineLoading(false));
  }

  useEffect(() => {
    if (tab === "history" && !history) {
      setHistoryLoading(true);
      getPropertyHistory(property.property_id)
        .then(setHistory)
        .finally(() => setHistoryLoading(false));
    }
    if (tab === "ai" && !explanation) {
      setExplanationLoading(true);
      setExplanationError(null);
      getPropertyExplanation(property.property_id)
        .then(setExplanation)
        .catch((e) => setExplanationError(e.message))
        .finally(() => setExplanationLoading(false));
    }
    if (tab === "ai" && !timeline && !timelineLoading) {
      runTimelineAnalysis();
    }
    if (tab === "charts" && !charts && !chartsLoading) {
      setChartsLoading(true);
      setChartsError(null);
      getPropertyCharts(property.property_id)
        .then(setCharts)
        .catch((e) => setChartsError(e.message))
        .finally(() => setChartsLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, property.property_id, history, explanation, timeline, charts]);

  const TABS: { id: Tab; label: string; icon: typeof Info }[] = [
    { id: "overview", label: "Overview", icon: Info },
    { id: "history", label: "History", icon: HistoryIcon },
    { id: "charts", label: "Charts", icon: LineChartIcon },
    { id: "ai", label: "AI Explanation", icon: Sparkles },
  ];

  return (
    <div>
      <div className="border-b border-slate-200 flex items-center justify-between gap-1">
        <div className="flex gap-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === t.id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <Icon size={16} />
              {t.label}
            </button>
          );
        })}
        </div>
        <a
          href={getReportUrl(property.property_id, "pdf")}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-indigo-600 mb-2 px-2 transition-colors"
        >
          <FileDown size={14} />
          Investor report (PDF)
        </a>
      </div>

      <div className="py-6">
        {tab === "overview" && (
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-slate-500 mb-2">
                Propensity Score
              </p>
              <ScoreBadge score={property.propensity_score} size="lg" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 mb-2">
                Key Drivers
              </p>
              {property.key_drivers && property.key_drivers.length > 0 ? (
                <ul className="space-y-2">
                  {property.key_drivers.map((d, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-slate-700 bg-slate-50 rounded-lg px-3 py-2 border border-slate-200"
                    >
                      <span className="text-indigo-500 mt-0.5">●</span>
                      {d}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-400">
                  No specific signals for this property yet.
                </p>
              )}
            </div>
          </div>
        )}

        {tab === "history" && (
          <div className="space-y-8">
            {historyLoading && (
              <p className="text-sm text-slate-400">Loading history...</p>
            )}
            {history && (
              <>
                <HistorySection title="Sales History (PPR)">
                  {history.sales_history.length === 0 && (
                    <EmptyRow text="No sale records." />
                  )}
                  {history.sales_history.map((s, i) => (
                    <div
                      key={i}
                      className="flex justify-between text-sm border-b border-slate-100 py-2"
                    >
                      <span>{formatDate(s.date_of_sale)}</span>
                      <span className="text-slate-500">{s.description}</span>
                      <span className="font-medium">{formatMoney(s.price)}</span>
                    </div>
                  ))}
                </HistorySection>

                <HistorySection title="Planning Permissions">
                  {history.planning_permissions.length === 0 && (
                    <EmptyRow text="No planning permissions." />
                  )}
                  {history.planning_permissions.map((p, i) => (
                    <div key={i} className="text-sm border-b border-slate-100 py-2">
                      <div className="flex justify-between">
                        <span className="font-medium">
                          {p.application_number} &middot; {p.category}
                        </span>
                        <span className="text-slate-500">
                          {formatDate(p.decision_date)}
                        </span>
                      </div>
                      <p className="text-slate-500 mt-0.5">{p.description}</p>
                    </div>
                  ))}
                </HistorySection>

                <HistorySection title="Derelict / Vacant Register">
                  {history.derelict_sites.length === 0 && (
                    <EmptyRow text="Not listed on any register." />
                  )}
                  {history.derelict_sites.map((d, i) => (
                    <div
                      key={i}
                      className="flex justify-between text-sm border-b border-slate-100 py-2"
                    >
                      <span>
                        {d.council} &middot; {d.register_ref}
                      </span>
                      <span className="text-slate-500">
                        {formatDate(d.entered_on_register_date)}
                      </span>
                      <span className="font-medium">{formatMoney(d.valuation)}</span>
                    </div>
                  ))}
                </HistorySection>

                <HistorySection title="Daft.ie Listings">
                  {history.daft_listings.length === 0 && (
                    <EmptyRow text="No listings." />
                  )}
                  {history.daft_listings.map((l, i) => (
                    <div key={i} className="text-sm border-b border-slate-100 py-2">
                      <div className="flex justify-between">
                        <span className="font-medium">
                          {l.category} ({l.listing_type})
                        </span>
                        <span className="text-slate-500">
                          {formatDate(l.scraped_at)}
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-500 mt-0.5">
                        <span>
                          {l.ber_rating ? `BER: ${l.ber_rating}` : ""}
                        </span>
                        <span>
                          {formatMoney(l.price)}{" "}
                          {l.sold_price ? `→ sold for ${formatMoney(l.sold_price)}` : ""}
                        </span>
                      </div>
                      {l.url && (
                        <a
                          href={l.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-600 hover:underline text-xs inline-flex items-center gap-1 mt-1"
                        >
                          View listing <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                  ))}
                </HistorySection>
              </>
            )}
          </div>
        )}

        {tab === "charts" && (
          <div className="space-y-6">
            {chartsLoading && (
              <p className="text-sm text-slate-400">Loading charts...</p>
            )}
            {chartsError && <p className="text-sm text-red-500">{chartsError}</p>}
            {charts && (
              <>
                <ChartCard title="Price History (PPR + Daft)">
                  {charts.price_history.length === 0 ? (
                    <EmptyRow text="No priced sale/listing events for this property." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <LineChart data={charts.price_history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis
                          dataKey="date"
                          tickFormatter={(d) => formatDate(d)}
                          fontSize={12}
                        />
                        <YAxis
                          tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`}
                          fontSize={12}
                          width={55}
                        />
                        <Tooltip
                          labelFormatter={(d) => formatDate(d as string)}
                          formatter={(value, _name, item) => [
                            formatMoney(value as number),
                            (item?.payload as { source?: string } | undefined)?.source ?? "",
                          ]}
                        />
                        <Line
                          type="monotone"
                          dataKey="price"
                          stroke="#4f46e5"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </ChartCard>

                <ChartCard title="Event Timeline">
                  {charts.event_timeline.length === 0 ? (
                    <EmptyRow text="No dated events recorded for this property." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <ScatterChart
                        margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis
                          dataKey="x"
                          type="number"
                          domain={["dataMin", "dataMax"]}
                          tickFormatter={(v) => new Date(v).toLocaleDateString("en-IE")}
                          fontSize={12}
                        />
                        <YAxis
                          dataKey="y"
                          type="category"
                          allowDuplicatedCategory={false}
                          fontSize={12}
                          width={100}
                        />
                        <Tooltip
                          labelFormatter={(v) => new Date(v as number).toLocaleDateString("en-IE")}
                          formatter={(_value, _name, item) => [item.payload.label, item.payload.y]}
                        />
                        <Scatter
                          data={charts.event_timeline.map((e) => ({
                            x: new Date(e.date).getTime(),
                            y: e.category,
                            label: e.label,
                          }))}
                          fill="#4f46e5"
                        />
                      </ScatterChart>
                    </ResponsiveContainer>
                  )}
                </ChartCard>

                <ChartCard title="Compared to Nearby Properties (5km)">
                  {!charts.area_comparison || charts.area_comparison.property_count === 0 ? (
                    <EmptyRow text="No nearby properties with GPS location to compare against." />
                  ) : (
                    <>
                      <ResponsiveContainer width="100%" height={180}>
                        <BarChart
                          data={[
                            { name: "This property", score: charts.propensity_score },
                            {
                              name: "Area average",
                              score: charts.area_comparison.avg_score ?? 0,
                            },
                          ]}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="name" fontSize={12} />
                          <YAxis domain={[0, 100]} fontSize={12} width={35} />
                          <Tooltip />
                          <Bar dataKey="score" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                      <p className="text-xs text-slate-400 mt-2">
                        Based on {charts.area_comparison.property_count} nearby
                        properties &middot; avg last sale price{" "}
                        {formatMoney(charts.area_comparison.avg_last_sale_price)}
                      </p>
                    </>
                  )}
                </ChartCard>

                <ChartCard title="Propensity Score Over Time">
                  {charts.score_history.length < 2 ? (
                    <EmptyRow text="Not enough history yet - this builds up as AI research/timeline analysis runs over time." />
                  ) : (
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={charts.score_history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis
                          dataKey="recorded_at"
                          tickFormatter={(d) => formatDate(d)}
                          fontSize={12}
                        />
                        <YAxis domain={[0, 100]} fontSize={12} width={35} />
                        <Tooltip labelFormatter={(d) => formatDate(d as string)} />
                        <Line
                          type="stepAfter"
                          dataKey="propensity_score"
                          stroke="#4f46e5"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </ChartCard>
              </>
            )}
          </div>
        )}

        {tab === "ai" && (
          <div>
            {explanationLoading && (
              <p className="text-sm text-slate-400">Generating explanation...</p>
            )}
            {explanationError && (
              <p className="text-sm text-red-500">{explanationError}</p>
            )}
            {explanation && (
              <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-5">
                <div className="flex items-center gap-2 text-indigo-600 font-medium text-sm mb-2">
                  <Sparkles size={16} />
                  AI Explanation (DeepSeek)
                </div>
                <p className="text-slate-700 leading-relaxed">
                  {explanation.explanation}
                </p>
              </div>
            )}

            <div className="mt-6 bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-slate-700 font-medium text-sm">
                  <Search size={16} />
                  Live Web Research
                </div>
                <button
                  onClick={() => runResearch(!!research)}
                  disabled={researchLoading}
                  className="text-xs font-medium px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {researchLoading
                    ? "Searching..."
                    : research
                    ? "Refresh search"
                    : "Search the web for this property"}
                </button>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                Looks up public mentions of this address (listings, local news,
                notices) and factors any genuine findings into the score.
                Cached for 30 days so it isn&apos;t re-searched every visit.
              </p>
              {researchError && (
                <p className="text-sm text-red-500">{researchError}</p>
              )}
              {research && (
                <div className="space-y-2">
                  <p className="text-xs text-slate-400">
                    {research.cached ? "Cached result from" : "Searched"}{" "}
                    {formatDate(research.researched_at)} &middot; score impact:{" "}
                    <span className="font-medium text-slate-600">
                      +{research.ai_signal_score}
                    </span>
                  </p>
                  {research.findings.length === 0 ? (
                    <EmptyRow text="No genuine public mentions found for this address." />
                  ) : (
                    research.findings.map((f, i) => (
                      <div
                        key={i}
                        className="text-sm bg-slate-50 border border-slate-200 rounded-lg px-3 py-2"
                      >
                        <p className="text-slate-700">{f.finding_summary}</p>
                        {f.source_url && (
                          <a
                            href={f.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:underline text-xs inline-flex items-center gap-1 mt-1"
                          >
                            Source <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            <div className="mt-6 bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-slate-700 font-medium text-sm">
                  <Brain size={16} />
                  Timeline Analysis (RAG + Chain-of-Thought)
                </div>
                <button
                  onClick={runTimelineAnalysis}
                  disabled={timelineLoading}
                  className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 disabled:opacity-50 transition-colors"
                >
                  {timelineLoading ? "Analyzing..." : "Re-analyze"}
                </button>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                Reasons only over facts already in our database (sales history,
                planning permissions, derelict/vacant status, Daft listings) -
                no web search, nothing invented. Runs automatically for every
                property alongside its propensity score.
              </p>
              {timelineLoading && !timeline && (
                <p className="text-sm text-slate-400">Analyzing timeline...</p>
              )}
              {timelineError && (
                <p className="text-sm text-red-500">{timelineError}</p>
              )}
              {timeline && (
                <div className="space-y-3">
                  <p className="text-xs text-slate-400">
                    Analyzed {formatDate(timeline.analyzed_at)} &middot; confidence:{" "}
                    <span className="font-medium text-slate-600">
                      {timeline.confidence}
                    </span>{" "}
                    &middot; score adjustment:{" "}
                    <span className="font-medium text-slate-600">
                      {timeline.score_adjustment >= 0 ? "+" : ""}
                      {timeline.score_adjustment}
                    </span>
                  </p>
                  <p className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                    {timeline.reasoning_summary}
                  </p>
                  {timeline.trigger_signals.length > 0 && (
                    <ul className="space-y-1.5">
                      {timeline.trigger_signals.map((s, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-2 text-sm text-slate-700"
                        >
                          <span className="text-indigo-500 mt-0.5">●</span>
                          {s}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HistorySection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-900 mb-2">{title}</h3>
      <div className="bg-white rounded-lg border border-slate-200 px-4">
        {children}
      </div>
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <p className="text-sm text-slate-400 py-3">{text}</p>;
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-slate-900 mb-3">{title}</h3>
      {children}
    </div>
  );
}
