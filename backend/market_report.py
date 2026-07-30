"""
market_report.py
-----------------
Čtvrtletní AI market report za CELÝ irský trh (rozšíření kroku 4 z
agentické pipeline - stejný princip jako investor report pro jednu
nemovitost, jen v měřítku celého trhu).

Pravidlo #1 (RAG): DeepSeek dostává výhradně reálné, předpočítané
agregáty z naší DB (`daft_quarterly_stats` - prodejní ceny/objemy podle
čtvrtletí z Daft.ie, `analytics_summary` - aktuální rozložení propensity
skóre) - žádná čísla si nedomýšlí.

Cache: jeden report na kalendářní čtvrtletí (`market_report_snapshots`,
UNIQUE(year, quarter)) - opakované volání bez force=True generování
nespouští znovu, jen vrátí uložený výsledek (stejný vzor jako
RESEARCH_TTL_DAYS u ai_research.py, jen granularita je "čtvrtletí"
místo dnů).
"""
import json
from datetime import datetime, timezone
from typing import Optional

from openai import OpenAI
from supabase import Client

from ai_schemas import MarketReportSections, call_deepseek_json

_SYSTEM_PROMPT = (
    "You are a market-analytics assistant for an Irish real estate platform. "
    "You are given ONLY real, pre-computed aggregate statistics from our own "
    "database: Daft.ie sold-price/sold-volume figures per quarter (going back "
    "several years) and the CURRENT distribution of our propensity-to-sell "
    "score across ~1 million tracked properties. Do not invent any number - "
    "reference only the figures given to you.\n\n"
    "Write three short Markdown sections for a quarterly market report:\n"
    "- market_overview: 2-4 sentences summarising the current state of the "
    "market based on the most recent quarter(s) of data.\n"
    "- trend_analysis: describe the trend across the given quarters (price "
    "direction, volume direction) - reference specific quarters/figures.\n"
    "- risk_assessment: 2-3 sentences on data limitations (e.g. Daft.ie sales "
    "data is a sample, not the full national register; recent quarters may "
    "be incomplete since they're still filling in) and how confident this "
    "reading of the market is.\n\n"
    "Respond with ONLY a JSON object: {\"market_overview\": str, "
    "\"trend_analysis\": str, \"risk_assessment\": str}"
)


def current_quarter(today: Optional[datetime] = None) -> tuple[int, int]:
    d = today or datetime.now(timezone.utc)
    return d.year, (d.month - 1) // 3 + 1


def _build_market_context(supabase: Client) -> dict:
    quarterly = (
        supabase.table("daft_quarterly_stats")
        .select("year,quarter,sold_count,avg_sold_price,median_sold_price")
        .order("year", desc=True)
        .order("quarter", desc=True)
        .limit(12)
        .execute()
    ).data
    quarterly = list(reversed(quarterly))  # chronological order for the model

    summary = (
        supabase.table("analytics_summary").select("*").limit(1).execute()
    ).data
    summary_row = summary[0] if summary else {}

    return {
        "quarterly_sold_stats_from_daft": quarterly,
        "current_propensity_score_distribution": {
            "total_properties": summary_row.get("total_properties"),
            "avg_score": summary_row.get("avg_score"),
            "score_bucket_0_10": summary_row.get("score_bucket_0_10"),
            "score_bucket_10_20": summary_row.get("score_bucket_10_20"),
            "score_bucket_20_30": summary_row.get("score_bucket_20_30"),
            "score_bucket_30_40": summary_row.get("score_bucket_30_40"),
            "score_bucket_40_50": summary_row.get("score_bucket_40_50"),
            "score_bucket_50_60": summary_row.get("score_bucket_50_60"),
            "score_bucket_60_70": summary_row.get("score_bucket_60_70"),
            "score_bucket_70_80": summary_row.get("score_bucket_70_80"),
            "score_bucket_80_90": summary_row.get("score_bucket_80_90"),
            "score_bucket_90_100": summary_row.get("score_bucket_90_100"),
        },
    }, quarterly


def generate_market_report(
    supabase: Client, ai_client: Optional[OpenAI], force: bool = False
) -> dict:
    year, quarter = current_quarter()

    if not force:
        cached = (
            supabase.table("market_report_snapshots")
            .select("*")
            .eq("year", year)
            .eq("quarter", quarter)
            .limit(1)
            .execute()
        ).data
        if cached:
            row = cached[0]
            _, quarterly = _build_market_context(supabase)
            return {
                "year": year,
                "quarter": quarter,
                "cached": True,
                "market_overview": row["market_overview"],
                "trend_analysis": row["trend_analysis"],
                "risk_assessment": row["risk_assessment"],
                "generated_at": row["generated_at"],
                "quarterly_stats": quarterly,
            }

    if not ai_client:
        raise ValueError("DEEPSEEK_API_KEY is not set - market report is unavailable.")

    context, quarterly = _build_market_context(supabase)
    sections = call_deepseek_json(
        ai_client,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=json.dumps(context, default=str, ensure_ascii=False),
        schema=MarketReportSections,
        temperature=0.3,
        max_tokens=800,
    )

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("market_report_snapshots").upsert(
        {
            "year": year,
            "quarter": quarter,
            "market_overview": sections.market_overview,
            "trend_analysis": sections.trend_analysis,
            "risk_assessment": sections.risk_assessment,
            "generated_at": now,
        },
        on_conflict="year,quarter",
    ).execute()

    return {
        "year": year,
        "quarter": quarter,
        "cached": False,
        "market_overview": sections.market_overview,
        "trend_analysis": sections.trend_analysis,
        "risk_assessment": sections.risk_assessment,
        "generated_at": now,
        "quarterly_stats": quarterly,
    }
