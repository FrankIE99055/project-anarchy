"""
timeline_analysis.py
---------------------
Krok 3 ("Pokročilá analytika a výpočet Propensity Score") z návrhu
agentické pipeline - Chain-of-Thought reasoning nad "časovou osou" jedné
nemovitosti (identifikované Eircode/adresou, NIKDY osobou).

Pravidlo #1 (RAG, žádné halucinace): DeepSeek nedostává žádné volné
zadání ani přístup k webu - jen strukturovaná fakta, která už máme v
databázi (sales_history, planning_permissions, derelict_sites,
daft_listings + předpočítané signály z `property_propensity_signals`).
Prompt modelu explicitně říká, že nesmí použít/domyslet žádný fakt, který
v timeline není.

Model smí interně "přemýšlet" v krocích (CoT), ale výstup musí být
POUZE strukturovaný JSON (`ai_schemas.TimelineAssessment`) - žádné
volné vysvětlování navíc, aby šlo bezpečně napojit na skóre a na
frontend.

Výsledek se ukládá do `ai_timeline_assessments` (audit trail) a do
`properties.timeline_signal_score` / `timeline_signal_note` /
`timeline_analyzed_at`, analogicky k existující web-research vrstvě
(`ai_research.py`). Finální skóre je
LEAST(100, percentile_score + ai_signal_score + timeline_signal_score).
"""
import json
from datetime import datetime, timezone
from typing import Optional

from openai import OpenAI
from supabase import Client

from ai_schemas import TimelineAssessment, call_deepseek_json

MAX_SCORE_ADJUSTMENT = 25

_SYSTEM_PROMPT = (
    "You are a real-estate propensity-to-sell reasoning engine for an Irish "
    "property analytics platform (Project Anarchy). You are given ONLY "
    "structured facts retrieved from our own database for ONE property, "
    "identified by address/Eircode - never by a person's name. This is "
    "Retrieval-Augmented reasoning: you MUST NOT invent, assume, or recall "
    "from general knowledge any fact that is not present in the JSON timeline "
    "you are given. If the timeline is sparse or empty, say so plainly and "
    "keep score_adjustment at or near 0 - do not compensate for missing data "
    "by guessing.\n\n"
    "Think step by step internally about how the facts interact using the "
    "'4 D' framework (Death, Divorce, Debt, Downsizing) as a lens - e.g. a "
    "long time since last sale, combined with a new retention planning "
    "application and a rental listing appearing after years of no activity, "
    "are the kinds of co-occurring anomalies that matter more together than "
    "alone. Your OUTPUT, however, must contain only the FINAL conclusion, not "
    "your intermediate reasoning steps.\n\n"
    "Respond with ONLY a JSON object matching this schema:\n"
    '{"reasoning_summary": "<2-3 sentence plain-English synthesis citing only '
    'given facts>", "trigger_signals": ["<short factual phrase>", ...] (max 8), '
    '"score_adjustment": <integer -10 to 25>, "confidence": "high"|"medium"|"low"}\n\n'
    "score_adjustment is a bonus/penalty on top of an already-computed base "
    "percentile score - use positive values only when the timeline shows a "
    "genuine, specific reason to expect a sale beyond what's already captured "
    "by the base signals; use 0 when the timeline is thin or inconclusive."
)


def build_timeline(supabase: Client, property_id: str) -> dict:
    """Sestaví strukturovaná fakta o jedné nemovitosti výhradně z naší DB
    (žádné externí vyhledávání) - vstup pro RAG reasoning.

    DŮLEŽITÉ: NEČTE se z view `property_propensity_signals` - to view
    agreguje přes CELÉ tabulky (sales_history/planning_permissions/...)
    ještě PŘED filtrem na jeden property_id, takže i dotaz na jedinou
    nemovitost přes PostgREST spolehlivě skončí na "statement timeout"
    (stejná třída chyby jako u map/percentile views - viz repo memory).
    Místo toho čteme jen `properties` (PK lookup, okamžité) a syrové
    řádky ze 4 tabulek přímo filtrované na property_id (indexované,
    stejný vzor jako už funkční /properties/{id}/history)."""
    prop = (
        supabase.table("properties")
        .select("address,eircode,percentile_score,raw_signal_score,base_key_drivers")
        .eq("id", property_id)
        .limit(1)
        .execute()
    ).data
    if not prop:
        raise ValueError("Property not found.")
    prop_row = prop[0]

    sales = (
        supabase.table("sales_history")
        .select("date_of_sale,price,description")
        .eq("property_id", property_id)
        .order("date_of_sale", desc=True)
        .execute()
    ).data

    planning = (
        supabase.table("planning_permissions")
        .select("category,application_type,decision_date,description")
        .eq("property_id", property_id)
        .order("decision_date", desc=True)
        .execute()
    ).data

    derelict = (
        supabase.table("derelict_sites")
        .select("council,entered_on_register_date,notice_date")
        .eq("property_id", property_id)
        .execute()
    ).data

    daft = (
        supabase.table("daft_listings")
        .select("listing_type,category,price,sold_price,sold_date,ber_rating,scraped_at")
        .eq("property_id", property_id)
        .order("scraped_at", desc=True)
        .execute()
    ).data

    return {
        "address": prop_row.get("address"),
        "eircode": prop_row.get("eircode"),
        "already_computed_base_score": prop_row.get("percentile_score"),
        "already_computed_key_drivers": prop_row.get("base_key_drivers") or [],
        "sales_history": sales,
        "planning_permissions": planning,
        "derelict_sites": derelict,
        "daft_listings": daft,
    }


def analyze_timeline(ai_client: OpenAI, timeline: dict) -> TimelineAssessment:
    return call_deepseek_json(
        ai_client,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=json.dumps(timeline, default=str, ensure_ascii=False),
        schema=TimelineAssessment,
        temperature=0.2,
        max_tokens=600,
    )


def run_timeline_analysis(
    supabase: Client,
    ai_client: Optional[OpenAI],
    property_id: str,
) -> dict:
    """Postaví timeline z DB, nechá DeepSeek udělat CoT reasoning a uloží
    výsledek (audit trail + skóre bonus na properties)."""
    if not ai_client:
        raise ValueError("DEEPSEEK_API_KEY is not set - timeline analysis is unavailable.")

    timeline = build_timeline(supabase, property_id)
    assessment = analyze_timeline(ai_client, timeline)

    score_adjustment = max(-10, min(MAX_SCORE_ADJUSTMENT, assessment.score_adjustment))
    now = datetime.now(timezone.utc).isoformat()

    supabase.table("ai_timeline_assessments").insert(
        {
            "property_id": property_id,
            "reasoning_summary": assessment.reasoning_summary,
            "trigger_signals": assessment.trigger_signals,
            "score_adjustment": score_adjustment,
            "confidence": assessment.confidence,
            "analyzed_at": now,
        }
    ).execute()

    prop = (
        supabase.table("properties")
        .select("percentile_score,ai_signal_score")
        .eq("id", property_id)
        .limit(1)
        .execute()
    ).data
    if not prop:
        raise ValueError("Property not found.")

    percentile_score = prop[0].get("percentile_score") or 0
    ai_signal_score = prop[0].get("ai_signal_score") or 0
    new_propensity_score = round(
        min(100, percentile_score + ai_signal_score + score_adjustment), 1
    )

    supabase.table("properties").update(
        {
            "timeline_signal_score": score_adjustment,
            "timeline_signal_note": assessment.reasoning_summary,
            "timeline_analyzed_at": now,
            "propensity_score": new_propensity_score,
        }
    ).eq("id", property_id).execute()

    supabase.table("property_score_history").insert(
        {
            "property_id": property_id,
            "propensity_score": new_propensity_score,
            "reason": f"Timeline analysis: {assessment.reasoning_summary}",
            "recorded_at": now,
        }
    ).execute()

    return {
        "property_id": property_id,
        "reasoning_summary": assessment.reasoning_summary,
        "trigger_signals": assessment.trigger_signals,
        "score_adjustment": score_adjustment,
        "confidence": assessment.confidence,
        "propensity_score": new_propensity_score,
        "analyzed_at": now,
    }
