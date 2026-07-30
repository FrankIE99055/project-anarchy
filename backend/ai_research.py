"""
ai_research.py
--------------
AI-research vrstva pro Project Anarchy.

Když si uživatel otevře nemovitost, tahle vrstva (na vyžádání, cachovaná)
nechá AI dohledat VEŘEJNÉ zmínky o KONKRÉTNÍ adrese na webu (inzeráty,
realitky, lokální zprávy, úřední oznámení) přes Tavily search API a
promítne nalezené fakty do skóre jako bonus nad rámec percentilového
základu.

Cache/TTL: výsledek se uloží do `ai_research_findings` + na `properties`
(ai_signal_score, ai_signal_note, ai_signal_researched_at). Pokud je
`ai_signal_researched_at` mladší než RESEARCH_TTL_DAYS, další request se
znovu neprohledává (nešahá znovu na Tavily/DeepSeek), jen vrátí to, co už
v DB je - viz `research_property(force=False)`.

GDPR: DeepSeek dostává explicitní instrukci nikdy neukládat/nezmiňovat
jména vlastníků/nájemníků, i kdyby byla ve zdrojovém textu - jen faktický
souhrn vázaný na adresu/nemovitost samotnou.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from openai import OpenAI
from supabase import Client

# Načte .env i při samostatném importu (nezávisle na tom, jestli ho už
# načetl main.py) - dotenv nepřepisuje proměnné, které už v prostředí jsou.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

RESEARCH_TTL_DAYS = 30
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
TAVILY_URL = "https://api.tavily.com/search"

MAX_SCORE_IMPACT = 20


class ResearchUnavailable(Exception):
    """TAVILY_API_KEY nebo AI klient není nastaven."""


def _search_web(address: str) -> list[dict]:
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": (
            f'"{address}" Ireland property for sale OR to let OR rent OR planning OR '
            "news OR auction OR probate OR receivership OR liquidation"
        ),
        "search_depth": "basic",
        "max_results": 8,
        "include_answer": False,
    }
    resp = requests.post(TAVILY_URL, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:500],
        }
        for r in data.get("results", [])
    ]


def _extract_findings_with_ai(ai_client: OpenAI, address: str, results: list[dict]) -> list[dict]:
    """Returns a list of 0-5 findings, each with its own finding text,
    signal_type (sale/rental/distress/other) and score_impact. Multiple
    genuine, distinct pieces of evidence about the same property (e.g. a
    current rental listing AND a separate planning dispute) are returned
    as separate entries instead of collapsing everything into one line."""
    prompt = (
        "You are a fact-extraction assistant for an Irish real estate analytics platform. "
        "You are given a property address and raw web search results about it. Irish "
        "addresses can be ambiguous (same townland name in multiple counties) - be "
        "CONSERVATIVE and only use a result if it is clearly about this specific property, "
        "not a different property, business, or the general area.\n\n"
        "NEVER include any person's name (owner, occupier, tenant, applicant) in your output, "
        "even if a name appears in the source text - refer only to 'the property' or "
        "'the owner' generically, or omit that detail entirely.\n\n"
        "Look for evidence relevant to EITHER of these two risks (a property can carry both):\n"
        "1) SALE risk - currently listed for sale, local news about a planning dispute, "
        "probate/estate notices, auction notices, receivership/liquidation, derelict/structural "
        "condition reports.\n"
        "2) RENTAL risk - currently listed to let/for rent, described as an investment/rental "
        "property, or any 'accidental landlord' signal (previously rented, may indicate the "
        "owner is not living there and could sell or re-list).\n\n"
        "If the search results contain several distinct, genuine pieces of evidence, return "
        "each as its OWN entry (up to 5) instead of merging them into one sentence.\n\n"
        "Respond with ONLY a JSON object, no other text:\n"
        '{"findings": [{"finding": "<one short factual sentence>", '
        '"signal_type": "sale"|"rental"|"distress"|"other", '
        '"score_impact": <integer 0-15>, "source_url": "<url of the matching result>"}]}\n'
        'Return {"findings": []} if there is no genuine evidence at all.\n\n'
        f"Address: {address}\n"
        f"Search results: {json.dumps(results, ensure_ascii=False)}"
    )

    response = ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500,
    )
    raw = response.choices[0].message.content.strip()
    # DeepSeek can wrap JSON in ```json fences despite instructions - strip them defensively.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[4:] if raw.lower().startswith("json") else raw
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []

    cleaned = []
    for f in (parsed.get("findings") or [])[:5]:
        if not f.get("finding"):
            continue
        impact = f.get("score_impact") or 0
        try:
            impact = max(0, min(15, int(impact)))
        except (TypeError, ValueError):
            impact = 0
        signal_type = f.get("signal_type") if f.get("signal_type") in ("sale", "rental", "distress", "other") else "other"
        cleaned.append({
            "finding": f.get("finding"),
            "signal_type": signal_type,
            "score_impact": impact,
            "source_url": f.get("source_url"),
        })
    return cleaned


def _is_cache_fresh(researched_at: Optional[str]) -> bool:
    if not researched_at:
        return False
    try:
        ts = datetime.fromisoformat(researched_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - ts < timedelta(days=RESEARCH_TTL_DAYS)


def research_property(
    supabase: Client,
    ai_client: Optional[OpenAI],
    property_id: str,
    force: bool = False,
) -> dict:
    """Vrátí AI-research nálezy pro danou nemovitost. Použije cache, pokud
    není starší než RESEARCH_TTL_DAYS a `force=False`; jinak zavolá Tavily +
    DeepSeek a výsledek uloží."""
    if not TAVILY_API_KEY or not ai_client:
        raise ResearchUnavailable(
            "TAVILY_API_KEY and/or DEEPSEEK_API_KEY is not set - AI research is unavailable."
        )

    prop = (
        supabase.table("properties")
        .select("id,address,percentile_score,base_key_drivers,ai_signal_score,ai_signal_note,ai_signal_researched_at")
        .eq("id", property_id)
        .limit(1)
        .execute()
    )
    if not prop.data:
        raise ValueError("Property not found.")
    row = prop.data[0]

    if not force and _is_cache_fresh(row.get("ai_signal_researched_at")):
        findings = (
            supabase.table("ai_research_findings")
            .select("title,source_url,finding_summary,score_impact,found_at")
            .eq("property_id", property_id)
            .order("found_at", desc=True)
            .execute()
        ).data
        return {
            "property_id": property_id,
            "cached": True,
            "ai_signal_score": row.get("ai_signal_score") or 0,
            "ai_signal_note": row.get("ai_signal_note"),
            "researched_at": row.get("ai_signal_researched_at"),
            "findings": findings,
        }

    results = _search_web(row["address"])
    findings_list = _extract_findings_with_ai(ai_client, row["address"], results)

    now = datetime.now(timezone.utc).isoformat()
    positive_findings = [f for f in findings_list if f["score_impact"] > 0]
    total_impact = min(MAX_SCORE_IMPACT, sum(f["score_impact"] for f in positive_findings))

    for f in findings_list:
        supabase.table("ai_research_findings").upsert(
            {
                "property_id": property_id,
                "source_url": f.get("source_url"),
                "title": f["finding"],
                "finding_summary": f["finding"],
                "score_impact": f["score_impact"],
                "found_at": now,
            },
            on_conflict="property_id,source_url",
        ).execute()

    base_key_drivers = row.get("base_key_drivers") or []
    # Findings only belong in "Key Drivers" (which implies they push the score
    # up) when they actually carried a positive score_impact - a finding like
    # "no evidence of imminent sale" is informative but must not appear as if
    # it were a reason for a high score.
    key_drivers = base_key_drivers + [f["finding"] for f in positive_findings]
    ai_signal_note = "; ".join(f["finding"] for f in positive_findings) or None
    percentile_score = row.get("percentile_score") or 0
    new_propensity_score = round(min(100, percentile_score + total_impact), 1)

    supabase.table("properties").update(
        {
            "ai_signal_score": total_impact,
            "ai_signal_note": ai_signal_note,
            "ai_signal_researched_at": now,
            "propensity_score": new_propensity_score,
            "key_drivers": key_drivers,
        }
    ).eq("id", property_id).execute()

    supabase.table("property_score_history").insert(
        {
            "property_id": property_id,
            "propensity_score": new_propensity_score,
            "reason": "Web research" + (f": {ai_signal_note}" if ai_signal_note else " (no new findings)"),
            "recorded_at": now,
        }
    ).execute()

    findings = (
        supabase.table("ai_research_findings")
        .select("title,source_url,finding_summary,score_impact,found_at")
        .eq("property_id", property_id)
        .order("found_at", desc=True)
        .execute()
    ).data

    return {
        "property_id": property_id,
        "cached": False,
        "ai_signal_score": total_impact,
        "ai_signal_note": ai_signal_note,
        "researched_at": now,
        "findings": findings,
    }
