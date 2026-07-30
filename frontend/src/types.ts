// Sdílené TypeScript typy odpovídající tvaru dat z backend API
// (d:\Project Anarchy\backend\main.py)

export interface PropertySummary {
  id: string;
  address: string;
  eircode: string | null;
  propensity_score: number;
  key_drivers: string[] | null;
}

export interface PropertyMapPoint {
  id: string;
  address: string;
  eircode: string | null;
  propensity_score: number;
  latitude: number;
  longitude: number;
}

export interface PropertySearchResponse {
  page: number;
  page_size: number;
  total: number;
  results: PropertySummary[];
}

export interface PropertyExplanation {
  property_id: string;
  propensity_score: number;
  key_drivers: string[];
  explanation: string;
}

export interface SaleHistoryEntry {
  date_of_sale: string | null;
  price: number | null;
  description: string | null;
}

export interface PlanningPermissionEntry {
  application_number: string;
  category: string | null;
  application_type: string | null;
  decision_date: string | null;
  description: string | null;
}

export interface DerelictSiteEntry {
  council: string;
  register_ref: string | null;
  entered_on_register_date: string | null;
  valuation: number | null;
}

export interface DaftListingEntry {
  listing_type: string | null;
  category: string | null;
  price: number | null;
  sold_price: number | null;
  sold_date: string | null;
  ber_rating: string | null;
  scraped_at: string | null;
  url: string | null;
}

export interface PropertyHistory {
  property_id: string;
  sales_history: SaleHistoryEntry[];
  planning_permissions: PlanningPermissionEntry[];
  derelict_sites: DerelictSiteEntry[];
  daft_listings: DaftListingEntry[];
}

export interface AiResearchFinding {
  title: string | null;
  source_url: string | null;
  finding_summary: string | null;
  score_impact: number;
  found_at: string;
}

export interface PropertyResearchResult {
  property_id: string;
  cached: boolean;
  ai_signal_score: number;
  ai_signal_note: string | null;
  researched_at: string | null;
  findings: AiResearchFinding[];
}

export interface TimelineAnalysisResult {
  property_id: string;
  reasoning_summary: string;
  trigger_signals: string[];
  score_adjustment: number;
  confidence: "high" | "medium" | "low";
  propensity_score: number;
  analyzed_at: string;
}

export interface PricePoint {
  date: string;
  price: number;
  source: string;
}

export interface TimelineEvent {
  date: string;
  category: string;
  label: string;
}

export interface AreaComparison {
  avg_score: number | null;
  avg_last_sale_price: number | null;
  property_count: number;
}

export interface ScoreHistoryPoint {
  propensity_score: number;
  reason: string | null;
  recorded_at: string;
}

export interface PropertyCharts {
  property_id: string;
  propensity_score: number;
  price_history: PricePoint[];
  event_timeline: TimelineEvent[];
  area_comparison: AreaComparison | null;
  score_history: ScoreHistoryPoint[];
}

export interface QuarterlyStat {
  year: number;
  quarter: number;
  sold_count: number;
  avg_sold_price: number | null;
  median_sold_price: number | null;
}

export interface MarketReport {
  year: number;
  quarter: number;
  cached: boolean;
  market_overview: string;
  trend_analysis: string;
  risk_assessment: string;
  generated_at: string;
  quarterly_stats: QuarterlyStat[];
}

export interface AnalyticsSummary {
  id: number;
  total_properties: number;
  properties_with_location: number;
  avg_score: number;
  score_bucket_0_10: number;
  score_bucket_10_20: number;
  score_bucket_20_30: number;
  score_bucket_30_40: number;
  score_bucket_40_50: number;
  score_bucket_50_60: number;
  score_bucket_60_70: number;
  score_bucket_70_80: number;
  score_bucket_80_90: number;
  score_bucket_90_100: number;
  with_retention: number;
  with_derelict_or_vacant: number;
  with_daft_signal: number;
  total_sales_history: number;
  total_planning_permissions: number;
  total_derelict_sites: number;
  total_daft_listings: number;
  computed_at: string;
}
