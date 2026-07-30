"""
prepare_planning_csv.py
-------------------------
Vyčistí raw_data/planning_raw.csv (stažené z ArcGIS REST API skriptem
download_planning.py) do formátu připraveného pro import do staging
tabulky `planning_staging` v Supabase (viz
database_schema/05_planning_staging_and_bulk_load.sql).

ArcGIS vrací data jako epoch milliseconds (int) - převádíme na ISO datum.
Adresy normalizujeme stejně jako u PPR (upper-case, ořez mezer), aby šla
zkusit shoda s properties.address.
"""
import os
import re
import pandas as pd

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
SOURCE_CSV = os.path.join(RAW_DATA_DIR, "planning_raw.csv")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "planning_clean.csv")
CHUNK_SIZE = 50_000

OUTPUT_COLUMNS = [
    "application_number", "planning_authority", "development_description",
    "development_address", "development_postcode", "application_type",
    "application_status", "decision", "land_use_code", "area_of_site",
    "num_residential_units", "one_off_house", "floor_area",
    "received_date", "decision_date", "grant_date", "expiry_date",
    "itm_easting", "itm_northing",
]


def normalize_address(address) -> str:
    if pd.isna(address):
        return ""
    return re.sub(r"\s+", " ", str(address)).strip().upper()


def epoch_ms_to_iso(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, unit="ms", errors="coerce", utc=True)
    return dt.dt.strftime("%Y-%m-%d").fillna("")


def main():
    if not os.path.exists(SOURCE_CSV):
        raise FileNotFoundError(f"Nenalezen {SOURCE_CSV}. Nejprve spusť download_planning.py")

    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)

    print(f"📄 Zpracovávám: {SOURCE_CSV}")
    total = 0
    first = True

    for chunk in pd.read_csv(SOURCE_CSV, chunksize=CHUNK_SIZE, dtype=str, on_bad_lines="skip"):
        total += len(chunk)

        out = pd.DataFrame({
            "application_number": chunk.get("ApplicationNumber", "").fillna(""),
            "planning_authority": chunk.get("PlanningAuthority", "").fillna(""),
            "development_description": chunk.get("DevelopmentDescription", "").fillna(""),
            "development_address": chunk.get("DevelopmentAddress", "").map(normalize_address),
            "development_postcode": chunk.get("DevelopmentPostcode", "").fillna(""),
            "application_type": chunk.get("ApplicationType", "").fillna(""),
            "application_status": chunk.get("ApplicationStatus", "").fillna(""),
            "decision": chunk.get("Decision", "").fillna(""),
            "land_use_code": chunk.get("LandUseCode", "").fillna(""),
            "area_of_site": chunk.get("AreaofSite", ""),
            "num_residential_units": chunk.get("NumResidentialUnits", ""),
            "one_off_house": chunk.get("OneOffHouse", "").fillna(""),
            "floor_area": chunk.get("FloorArea", ""),
            "received_date": epoch_ms_to_iso(chunk.get("ReceivedDate")),
            "decision_date": epoch_ms_to_iso(chunk.get("DecisionDate")),
            "grant_date": epoch_ms_to_iso(chunk.get("GrantDate")),
            "expiry_date": epoch_ms_to_iso(chunk.get("ExpiryDate")),
            "itm_easting": chunk.get("ITMEasting", ""),
            "itm_northing": chunk.get("ITMNorthing", ""),
        }, columns=OUTPUT_COLUMNS)

        out = out[out["application_number"].str.strip() != ""]

        out.to_csv(OUTPUT_CSV, mode="a", header=first, index=False, encoding="utf-8")
        first = False
        print(f"  ↳ zpracováno {total}...")

    print(f"✅ Hotovo! {OUTPUT_CSV} připraveno k importu.")


if __name__ == "__main__":
    main()
