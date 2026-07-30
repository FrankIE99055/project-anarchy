"""
property_charts.py
-------------------
Podklady pro "Charts" tab u jedné nemovitosti. Žádné nové AI volání -
jen poskládání dat, která už v DB máme, do tvaru vhodného pro grafy:

- price_history: sloučené PPR prodeje + Daft sold ceny v čase
- event_timeline: všechny události (prodej/planning/derelict/Daft) na
  jedné časové ose
- area_comparison: průměrné skóre/cena nemovitostí v okruhu 5 km
  (viz `nearby_area_stats` SQL funkce, používá GIST index - rychlé)
- score_history: vývoj propensity_score v čase (zapisuje se při každé
  AI-driven změně skóre, viz ai_research.py / timeline_analysis.py)
"""
from supabase import Client


def get_property_charts(supabase: Client, property_id: str) -> dict:
    prop = (
        supabase.table("properties")
        .select("id,address,propensity_score")
        .eq("id", property_id)
        .limit(1)
        .execute()
    ).data
    if not prop:
        raise ValueError("Property not found.")

    sales = (
        supabase.table("sales_history")
        .select("date_of_sale,price")
        .eq("property_id", property_id)
        .order("date_of_sale")
        .execute()
    ).data

    daft = (
        supabase.table("daft_listings")
        .select("price,sold_price,sold_date,listing_type,category,scraped_at")
        .eq("property_id", property_id)
        .order("scraped_at")
        .execute()
    ).data

    planning = (
        supabase.table("planning_permissions")
        .select("decision_date,category,application_number")
        .eq("property_id", property_id)
        .execute()
    ).data

    derelict = (
        supabase.table("derelict_sites")
        .select("entered_on_register_date,notice_date,council")
        .eq("property_id", property_id)
        .execute()
    ).data

    score_history = (
        supabase.table("property_score_history")
        .select("propensity_score,reason,recorded_at")
        .eq("property_id", property_id)
        .order("recorded_at")
        .execute()
    ).data

    price_history = []
    for s in sales:
        if s.get("date_of_sale") and s.get("price"):
            price_history.append(
                {"date": s["date_of_sale"], "price": s["price"], "source": "PPR sale"}
            )
    for d in daft:
        if d.get("sold_date") and d.get("sold_price"):
            price_history.append(
                {"date": d["sold_date"], "price": d["sold_price"], "source": "Daft sold"}
            )
    price_history.sort(key=lambda r: r["date"])

    event_timeline = []
    for s in sales:
        if s.get("date_of_sale"):
            event_timeline.append(
                {"date": s["date_of_sale"], "category": "Sale", "label": "PPR sale"}
            )
    for p in planning:
        if p.get("decision_date"):
            event_timeline.append(
                {
                    "date": p["decision_date"],
                    "category": "Planning",
                    "label": p.get("category") or p.get("application_number") or "Planning permission",
                }
            )
    for d in derelict:
        date = d.get("entered_on_register_date") or d.get("notice_date")
        if date:
            event_timeline.append(
                {
                    "date": date,
                    "category": "Derelict/Vacant",
                    "label": d.get("council") or "Derelict/Vacant register",
                }
            )
    for d in daft:
        if d.get("scraped_at"):
            label = f"{d.get('category') or 'Listing'} ({d.get('listing_type') or 'n/a'})"
            event_timeline.append(
                {"date": d["scraped_at"], "category": "Daft listing", "label": label}
            )
    event_timeline.sort(key=lambda r: r["date"])

    area = None
    try:
        area_result = (
            supabase.rpc(
                "nearby_area_stats", {"target_property_id": property_id, "radius_m": 5000}
            )
            .execute()
            .data
        )
        if area_result:
            area = area_result[0]
    except Exception:
        area = None

    return {
        "property_id": property_id,
        "propensity_score": prop[0].get("propensity_score"),
        "price_history": price_history,
        "event_timeline": event_timeline,
        "area_comparison": area,
        "score_history": score_history,
    }
