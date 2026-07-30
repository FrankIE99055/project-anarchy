"""
download_townlands.py
----------------------
Stáhne celonárodní databázi townlandů (Townlands - National Placenames
Gazetteer) z Tailte Éireann ArcGIS REST API. Jde o bod (centroid) pro
každý townland v Irsku - CC BY 4.0 licence, 50 380 záznamů.

Zdroj: https://services-eu1.arcgis.com/FH5XCsx8rYXqnjF5/arcgis/rest/services/Townlands___OSi_National_Placenames_Gazetteer/FeatureServer/0

Použití: mnoho adres v PPR je zapsáno jen jako "TOWNLAND, PARISH" (bez
Eircode, bez GPS) - přiřazením souřadnic townlandu (i když jen přibližných,
na úrovni townlandu) dostaneme nemovitosti bez GPS aspoň zhruba na mapu.

Stahuje po stránkách (max 2000/request, ~26 requestů) do
raw_data/townlands_raw.csv.
"""
import os
import time
import requests
import pandas as pd

BASE_URL = (
    "https://services-eu1.arcgis.com/FH5XCsx8rYXqnjF5/arcgis/rest/services/"
    "Townlands___OSi_National_Placenames_Gazetteer/FeatureServer/0/query"
)

OUT_FIELDS = ["English_Na", "County", "ITM_E", "ITM_N"]

PAGE_SIZE = 2000
RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "townlands_raw.csv")


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
        "orderByFields": "OBJECTID_1",
        "f": "json",
    }
    for attempt in range(3):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
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
    print(f"📡 Celkem townlandů: {total}")

    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)

    offset = 0
    written = 0
    first = True
    while offset < total:
        rows = fetch_page(offset)
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
