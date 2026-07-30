"""
report_generation.py
---------------------
Krok 4 ("Automatizovaný reporting pro investory") z návrhu agentické
pipeline. Vezme už vypočtená, čistá data o nemovitosti (skóre, key
drivers, poslední timeline reasoning, pokud existuje) a nechá DeepSeek
přeložit je do srozumitelného textu - STÁLE podle pravidla #1 (RAG):
model dostává jen fakta z DB, nic si nedomýšlí a nesmí zmínit žádné
jméno osoby (GDPR, stejně jako zbytek AI vrstvy v tomhle projektu).

Výstup je strukturovaný (`ai_schemas.InvestorReportSections`), aby šel
spolehlivě poskládat do Markdownu a odtud do PDF (přes xhtml2pdf - čistě
pythonová knihovna bez nativních závislostí, funguje i na Windows bez
dalšího instalování).
"""
import io
from datetime import datetime, timezone
from typing import Optional

import markdown as markdown_lib
from openai import OpenAI
from supabase import Client
from xhtml2pdf import pisa

from ai_schemas import InvestorReportSections, call_deepseek_json

_SYSTEM_PROMPT = (
    "You are a report-writing assistant for a real-estate investment analytics "
    "platform. You are given ONLY factual, already-computed data about ONE "
    "property (address/Eircode, a 0-100 propensity-to-sell score, a list of "
    "specific data-driven key drivers, and optionally an AI timeline reasoning "
    "summary). Do not invent any fact that isn't given to you. NEVER mention any "
    "person's name (owner/occupier/tenant) even if one appears in the input - "
    "refer only to 'the property' or 'the owner' generically.\n\n"
    "Write three short Markdown sections for a professional investor report:\n"
    "- property_overview: 2-4 sentences describing the property and its current "
    "propensity score in plain English.\n"
    "- trigger_signals_analysis: explain WHY the score is what it is, referencing "
    "only the given key drivers / timeline reasoning - use a short bullet list if "
    "there are multiple drivers.\n"
    "- risk_assessment: 2-3 sentences on how confident/uncertain this assessment "
    "is (e.g. note if data is sparse, if this is a probabilistic heuristic rather "
    "than a certainty, and any caveats).\n\n"
    "Respond with ONLY a JSON object: {\"property_overview\": str, "
    "\"trigger_signals_analysis\": str, \"risk_assessment\": str}"
)


def _build_context(supabase: Client, property_id: str) -> dict:
    prop = (
        supabase.table("properties")
        .select(
            "id,address,eircode,propensity_score,key_drivers,"
            "timeline_signal_note,timeline_analyzed_at"
        )
        .eq("id", property_id)
        .limit(1)
        .execute()
    ).data
    if not prop:
        raise ValueError("Property not found.")
    return prop[0]


def _generate_sections(ai_client: OpenAI, context: dict) -> InvestorReportSections:
    user_prompt = (
        f"Address: {context.get('address')}\n"
        f"Eircode: {context.get('eircode') or 'unknown'}\n"
        f"Propensity score: {context.get('propensity_score')}/100\n"
        f"Key drivers: {', '.join(context.get('key_drivers') or []) or 'none recorded'}\n"
        f"Timeline reasoning (if any): {context.get('timeline_signal_note') or 'not analyzed yet'}"
    )
    return call_deepseek_json(
        ai_client,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=InvestorReportSections,
        temperature=0.3,
        max_tokens=700,
    )


def generate_report_markdown(
    supabase: Client, ai_client: Optional[OpenAI], property_id: str
) -> str:
    """Vrátí kompletní investorský report jako Markdown text."""
    if not ai_client:
        raise ValueError("DEEPSEEK_API_KEY is not set - report generation is unavailable.")

    context = _build_context(supabase, property_id)
    sections = _generate_sections(ai_client, context)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        f"# Investor Report - {context.get('address')}\n\n"
        f"*Generated {generated_at} - Project Anarchy*\n\n"
        f"**Propensity Score:** {context.get('propensity_score')}/100\n\n"
        "## Property Overview\n\n"
        f"{sections.property_overview}\n\n"
        "## Trigger Signals Analysis\n\n"
        f"{sections.trigger_signals_analysis}\n\n"
        "## Risk Assessment\n\n"
        f"{sections.risk_assessment}\n"
    )


def markdown_to_pdf(markdown_text: str) -> bytes:
    """Převede Markdown report na PDF bytes (přes HTML)."""
    html = markdown_lib.markdown(markdown_text)
    styled_html = (
        "<html><head><meta charset='utf-8'><style>"
        "body { font-family: Helvetica, Arial, sans-serif; font-size: 12px; }"
        "h1 { font-size: 20px; } h2 { font-size: 15px; color: #333; }"
        "</style></head><body>" + html + "</body></html>"
    )
    buffer = io.BytesIO()
    result = pisa.CreatePDF(src=styled_html, dest=buffer)
    if result.err:
        raise ValueError("Failed to render PDF from report Markdown.")
    return buffer.getvalue()
