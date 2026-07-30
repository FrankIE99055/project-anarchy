"""
main.py
--------
Project Anarchy - backend API (FastAPI).

Poskytuje:
- GET /properties/{property_id}          - základní info + skóre + key_drivers
- GET /properties/{property_id}/explain   - lidsky čitelné AI vysvětlení skóre (DeepSeek)
- GET /properties/top                     - top N nemovitostí podle skóre

AI middleware (DeepSeek) se používá VÝHRADNĚ k přeformulování už existujících,
databází vypočtených `key_drivers` do plynulé věty - AI si signály/skóre
nevymýšlí ani je sama nepočítá, jen je srozumitelně popisuje. To udržuje
model vysvětlitelný a auditovatelný (žádná černá skříňka).
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from dotenv import load_dotenv
from pydantic import BaseModel
from supabase import create_client, Client
from openai import OpenAI

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

import address_cleaning
import ai_research
import market_report
import property_charts
import report_generation
import timeline_analysis

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ai_client: Optional[OpenAI] = (
    OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL) if DEEPSEEK_API_KEY else None
)

app = FastAPI(title="Project Anarchy API", version="0.1.0")

# Lokální vývoj - Next.js dev server běží na jiném portu (CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROPERTY_FIELDS = "id,address,eircode,propensity_score,key_drivers"


def get_property_score(property_id: str) -> dict:
    result = (
        supabase.table("properties")
        .select("id,address,eircode,propensity_score,key_drivers")
        .eq("id", property_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Property not found or has no computed score.")
    row = result.data[0]
    return {
        "property_id": row["id"],
        "address": row["address"],
        "eircode": row["eircode"],
        "propensity_score": row["propensity_score"],
        "key_drivers": row.get("key_drivers") or [],
    }


@app.get("/properties/top")
def top_properties(limit: int = Query(50, le=500)):
    result = (
        supabase.table("properties")
        .select("id,address,eircode,propensity_score,key_drivers")
        .order("propensity_score", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@app.get("/properties/map")
def properties_for_map(
    limit: int = Query(1000, le=5000),
    min_score: float = Query(0, ge=0, le=100),
):
    """Nemovitosti s GPS polohou pro vykreslení na mapě.

    Používá deterministický stratifikovaný výběr (`bucket_rank` z view
    `properties_map`, viz 17/18_map_*.sql): pro každý decil skóre
    (0-10, 10-20, ..., 90-100) vezme jen prvních `limit/10` nemovitostí.
    Bez tohohle by "seřadit podle skóre sestupně a vzít top N" vracelo
    jen nemovitosti z jedné obří plošiny stejného skóre (po percentilovém
    přepočtu jich je desetitisíce se STEJNOU hodnotou) - výsledkem by
    byly samé stejnobarevné body na mapě.

    DŮLEŽITÉ: řadíme podle `bucket_rank` (ne podle propensity_score
    sestupně!) - Supabase/PostgREST má tvrdý strop 1000 řádků na
    odpověď (db-max-rows), takže řazení podle skóre by tenhle strop
    ořízlo o nejnižší decily úplně (odřízly by se jako "poslední" podle
    score). Řazením podle bucket_rank dostaneme rank=1 z KAŽDÉHO decilu
    první, pak rank=2 z každého atd. - i po oříznutí na 1000 řádků tak
    zůstane rovnoměrné zastoupení celé barevné škály.
    """
    per_bucket = max(1, limit // 10)
    result = (
        supabase.table("properties_map")
        .select("id,address,eircode,propensity_score,latitude,longitude")
        .gte("propensity_score", min_score)
        .lte("bucket_rank", per_bucket)
        .order("bucket_rank")
        .limit(limit)
        .execute()
    )
    return result.data


@app.get("/properties")
def search_properties(
    q: Optional[str] = Query(None, description="Hledaný text v adrese nebo Eircode"),
    min_score: float = Query(0, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, le=100),
):
    """Vyhledávání/výpis nemovitostí s textovým filtrem a stránkováním.

    POZOR na `count`: "exact" dělal skutečný COUNT(*) přes filtrovanou
    množinu - u běžných substringů (např. "Dublin" - 261k+ shod z 1.43M
    nemovitostí po OSM importu) to trvalo přes 8s a naráželo na PostgRESTův
    statement timeout (stejná třída chyby jako u map/percentile views).
    "estimated" použije odhad z query poplánovače misto skutečného počítání
    (přesné pro malé/filtrované výsledky, jen odhad pro velké) - stránkování
    zůstává použitelné, ale bez risku timeoutu."""
    query = supabase.table("properties").select(PROPERTY_FIELDS, count="estimated")
    if q:
        query = query.or_(f"address.ilike.%{q}%,eircode.ilike.%{q}%")
    if min_score > 0:
        query = query.gte("propensity_score", min_score)

    start = (page - 1) * page_size
    end = start + page_size - 1
    result = query.order("propensity_score", desc=True).range(start, end).execute()

    return {
        "page": page,
        "page_size": page_size,
        "total": result.count,
        "results": result.data,
    }


@app.get("/properties/{property_id}")
def get_property(property_id: str):
    return get_property_score(property_id)


@app.get("/properties/{property_id}/history")
def property_history(property_id: str):
    """Sloučená časová historie ze všech zdrojů pro jednu nemovitost -
    prodeje (PPR), stavební povolení, chátrající/prázdné registry a
    Daft inzeráty."""
    sales = (
        supabase.table("sales_history")
        .select("date_of_sale,price,description")
        .eq("property_id", property_id)
        .order("date_of_sale", desc=True)
        .execute()
    ).data

    planning = (
        supabase.table("planning_permissions")
        .select("application_number,category,application_type,decision_date,description")
        .eq("property_id", property_id)
        .order("decision_date", desc=True)
        .execute()
    ).data

    derelict = (
        supabase.table("derelict_sites")
        .select("council,register_ref,entered_on_register_date,valuation")
        .eq("property_id", property_id)
        .execute()
    ).data

    daft = (
        supabase.table("daft_listings")
        .select("listing_type,category,price,sold_price,sold_date,ber_rating,scraped_at,url")
        .eq("property_id", property_id)
        .order("scraped_at", desc=True)
        .execute()
    ).data

    return {
        "property_id": property_id,
        "sales_history": sales,
        "planning_permissions": planning,
        "derelict_sites": derelict,
        "daft_listings": daft,
    }


@app.get("/analytics/summary")
def analytics_summary():
    result = supabase.table("analytics_summary").select("*").limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Analytics have not been computed yet.")
    return result.data[0]


@app.get("/properties/{property_id}/explain")
def explain_property(property_id: str):
    row = get_property_score(property_id)
    key_drivers = row.get("key_drivers") or []
    score = row.get("propensity_score")
    address = row.get("address")

    if not ai_client:
        raise HTTPException(
            status_code=503,
            detail="DEEPSEEK_API_KEY is not set - AI explanation is unavailable.",
        )

    if not key_drivers:
        return {
            "property_id": property_id,
            "propensity_score": score,
            "key_drivers": [],
            "explanation": "We don't have any specific signals for this property yet.",
        }

    prompt = (
        "You are an assistant for a real estate analytics application. You will "
        "receive an address, a propensity-to-sell score (0-100), and a list of "
        "specific data signals that contributed to this score. Write ONE short "
        "paragraph (2-3 sentences) in English that clearly explains why the "
        "property received this score. Stick to the FACTS in the signal list - "
        "do not make anything up or add information that isn't there.\n\n"
        f"Address: {address}\n"
        f"Score: {score}/100\n"
        f"Signals: {', '.join(key_drivers)}"
    )

    response = ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200,
    )
    explanation = response.choices[0].message.content.strip()

    return {
        "property_id": property_id,
        "propensity_score": score,
        "key_drivers": key_drivers,
        "explanation": explanation,
    }


@app.post("/properties/{property_id}/research")
def research_property(property_id: str, force: bool = Query(False)):
    """Nechá AI dohledat veřejné zmínky o téhle konkrétní adrese na webu
    (Tavily search + DeepSeek extrakce faktů) a promítne nález do skóre.
    Cachováno na RESEARCH_TTL_DAYS - opakované volání bez force=true
    nešahá znovu na externí API, jen vrátí uložený výsledek."""
    try:
        return ai_research.research_property(supabase, ai_client, property_id, force=force)
    except ai_research.ResearchUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class CleanAddressRequest(BaseModel):
    raw_address: str


@app.post("/addresses/clean")
def clean_address_endpoint(body: CleanAddressRequest):
    """Krok 2 agentické pipeline: vyčistí/normalizuje syrový text adresy
    a GDPR-redaktuje jméno osoby, pokud se v něm omylem objeví. NIKDY
    nevrací/nevymýšlí Eircode - viz address_cleaning.py."""
    if not ai_client:
        raise HTTPException(
            status_code=503,
            detail="DEEPSEEK_API_KEY is not set - address cleaning is unavailable.",
        )
    try:
        return address_cleaning.clean_address(ai_client, body.raw_address).model_dump()
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/properties/{property_id}/timeline-analysis")
def timeline_analysis_endpoint(property_id: str):
    """Krok 3 agentické pipeline: RAG + Chain-of-Thought analýza celé
    'časové osy' nemovitosti (prodeje/planning/derelict/Daft), NE web
    search jako /research - jen fakta z naší vlastní DB. Výsledek se
    promítne do properties.timeline_signal_score a propensity_score."""
    try:
        return timeline_analysis.run_timeline_analysis(supabase, ai_client, property_id)
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "not found" in detail.lower() else 502
        if not ai_client:
            status_code = 503
        raise HTTPException(status_code=status_code, detail=detail)


@app.get("/properties/{property_id}/report")
def property_report(property_id: str, format: str = Query("markdown", pattern="^(markdown|pdf)$")):
    """Krok 4 agentické pipeline: automatizovaný investorský report
    (Property Overview / Trigger Signals Analysis / Risk Assessment),
    poskládaný výhradně z už vypočtených dat v DB. format=markdown vrací
    text, format=pdf vrátí vygenerované PDF ke stažení."""
    try:
        md = report_generation.generate_report_markdown(supabase, ai_client, property_id)
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "not found" in detail.lower() else 502
        if not ai_client:
            status_code = 503
        raise HTTPException(status_code=status_code, detail=detail)

    if format == "markdown":
        return Response(content=md, media_type="text/markdown")

    pdf_bytes = report_generation.markdown_to_pdf(md)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{property_id}.pdf"'},
    )


@app.get("/properties/{property_id}/charts")
def property_charts_endpoint(property_id: str):
    """Podklady pro 'Charts' tab u jedné nemovitosti: cenová historie
    (PPR + Daft), timeline všech událostí, srovnání s okolím (5 km) a
    historie vývoje propensity_score. Žádné nové AI volání."""
    try:
        return property_charts.get_property_charts(supabase, property_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/market-report")
def market_report_endpoint(force: bool = Query(False)):
    """Čtvrtletní AI market report za celý irský trh (Daft.ie prodejní
    ceny/objemy podle čtvrtletí + aktuální rozložení propensity skóre).
    Cachováno na kalendářní čtvrtletí - force=true vynutí přegenerování."""
    try:
        return market_report.generate_market_report(supabase, ai_client, force=force)
    except ValueError as e:
        status_code = 503 if not ai_client else 502
        raise HTTPException(status_code=status_code, detail=str(e))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ai_enabled": ai_client is not None,
        "ai_research_enabled": ai_client is not None and bool(ai_research.TAVILY_API_KEY),
    }
