"""
download_planning.py
---------------------
Stáhne KOMPLETNÍ národní databázi stavebních povolení (National Planning
Applications) z irského ArcGIS REST API (data.gov.ie / data-housinggovie).

Zdroj: https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/IrishPlanningApplications/FeatureServer/0

DŮLEŽITÉ (GDPR): Dataset obsahuje i osobní údaje žadatelů (ApplicantForename,
ApplicantSurname, ApplicantAddress). Ty se ZÁMĚRNĚ NESTAHUJÍ - pracujeme
pouze s adresou nemovitosti / stavebním povolením, ne s konkrétními lidmi.

Stahuje po stránkách (max 2000 záznamů na request, ~250 requestů na celý
dataset) a ukládá do raw_data/planning_raw.csv.
"""
import os
import time
import requests
import pandas as pd

from self_healing import run_with_self_healing

BASE_URL = "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/IrishPlanningApplications/FeatureServer/0/query"

# Vzorek posledního syrového JSON, který scraper viděl - aktualizuje se při
# každém requestu ve fetch_page(). Použije se jako kontext pro DeepSeek,
# pokud fetch_page nakonec selže (viz self_healing.run_with_self_healing).
_last_response_text = ""

# Pouze pole vztažená k nemovitosti / povolení - žádné osobní údaje žadatele.
OUT_FIELDS = [
    "ApplicationNumber",
    "PlanningAuthority",
    "DevelopmentDescription",
    "DevelopmentAddress",
    "DevelopmentPostcode",
    "ApplicationType",
    "ApplicationStatus",
    "Decision",
    "LandUseCode",
    "AreaofSite",
    "NumResidentialUnits",
    "OneOffHouse",
    "FloorArea",
    "ReceivedDate",
    "DecisionDate",
    "GrantDate",
    "ExpiryDate",
    "ITMEasting",
    "ITMNorthing",
]

PAGE_SIZE = 2000
RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "planning_raw.csv")


def fetch_total_count() -> int:
    resp = requests.get(BASE_URL, params={"where": "1=1", "returnCountOnly": "true", "f": "json"}, timeout=60)
    resp.raise_for_status()
    return resp.json()["count"]


def fetch_page(offset: int) -> list[dict]:
    params = {
        "where": "1=1",
        "outFields": ",".join(OUT_FIELDS),
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "orderByFields": "OBJECTID",
        "f": "json",
    }
    global _last_response_text
    for attempt in range(3):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            _last_response_text = resp.text[:4000]
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return [f["attributes"] for f in data.get("features", [])]
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  ⚠️ chyba na offsetu {offset}, zkouším znovu ({e})")
            time.sleep(2)


def main():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    total = fetch_total_count()
    print(f"📡 Celkem záznamů v National Planning Applications: {total}")

    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)

    offset = 0
    written = 0
    first = True
    while offset < total:
        # Sebe-opravující se scraper (krok 1 agentické pipeline): pokud
        # fetch_page po 3 pokusech selže (ArcGIS API/schéma se změnilo),
        # DeepSeek dostane traceback + poslední syrovou odpověď a NÁVRH
        # opravy se jen uloží do self_heal_suggestions/ pro kontrolu
        # člověkem - výjimka se vždy znovu vyhodí, scraper se nikdy tiše
        # "neopraví" sám. Viz self_healing.py.
        rows = run_with_self_healing(
            "download_planning.py",
            fetch_page,
            offset,
            context_sample_fn=lambda: _last_response_text,
        )
        if not rows:
            break
        df = pd.DataFrame(rows, columns=OUT_FIELDS)
        df.to_csv(OUTPUT_CSV, mode="a", header=first, index=False, encoding="utf-8")
        first = False
        written += len(rows)
        offset += PAGE_SIZE
        print(f"  ↳ staženo {written}/{total}...")

    print(f"✅ Hotovo! {OUTPUT_CSV} obsahuje {written} záznamů.")


if __name__ == "__main__":
    main()
