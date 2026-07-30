// Malý typovaný klient pro Project Anarchy backend API.

import type {
  AnalyticsSummary,
  MarketReport,
  PropertyCharts,
  PropertyExplanation,
  PropertyHistory,
  PropertyMapPoint,
  PropertyResearchResult,
  PropertySearchResponse,
  PropertySummary,
  TimelineAnalysisResult,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function apiFetch<T>(path: string, revalidateSeconds = 0): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    next: revalidateSeconds ? { revalidate: revalidateSeconds } : undefined,
    cache: revalidateSeconds ? undefined : "no-store",
  });
  if (!res.ok) {
    throw new Error(`API chyba ${res.status} na ${path}`);
  }
  return res.json();
}

export function getTopProperties(limit = 50) {
  return apiFetch<PropertySummary[]>(`/properties/top?limit=${limit}`);
}

export function getPropertiesForMap(limit = 1000, minScore = 0) {
  return apiFetch<PropertyMapPoint[]>(
    `/properties/map?limit=${limit}&min_score=${minScore}`
  );
}

export function searchProperties(params: {
  q?: string;
  minScore?: number;
  page?: number;
  pageSize?: number;
}) {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.minScore) search.set("min_score", String(params.minScore));
  search.set("page", String(params.page ?? 1));
  search.set("page_size", String(params.pageSize ?? 25));
  return apiFetch<PropertySearchResponse>(`/properties?${search.toString()}`);
}

export function getProperty(id: string) {
  return apiFetch<PropertySummary & { property_id: string }>(`/properties/${id}`);
}

export function getPropertyExplanation(id: string) {
  return apiFetch<PropertyExplanation>(`/properties/${id}/explain`);
}

export function getPropertyHistory(id: string) {
  return apiFetch<PropertyHistory>(`/properties/${id}/history`);
}

export function getAnalyticsSummary() {
  return apiFetch<AnalyticsSummary>("/analytics/summary");
}

export async function researchProperty(id: string, force = false) {
  const res = await fetch(
    `${API_URL}/properties/${id}/research?force=${force}`,
    { method: "POST", cache: "no-store" }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `API chyba ${res.status} na /properties/${id}/research`);
  }
  return res.json() as Promise<PropertyResearchResult>;
}

export async function analyzeTimeline(id: string) {
  const res = await fetch(`${API_URL}/properties/${id}/timeline-analysis`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(
      body?.detail || `API chyba ${res.status} na /properties/${id}/timeline-analysis`
    );
  }
  return res.json() as Promise<TimelineAnalysisResult>;
}

export function getReportUrl(id: string, format: "markdown" | "pdf" = "pdf") {
  return `${API_URL}/properties/${id}/report?format=${format}`;
}

export function getPropertyCharts(id: string) {
  return apiFetch<PropertyCharts>(`/properties/${id}/charts`);
}

export function getMarketReport(force = false) {
  return apiFetch<MarketReport>(`/market-report?force=${force}`);
}
