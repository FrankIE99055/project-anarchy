"""
prepare_daft_csv.py
---------------------
Vyčistí raw_data/daft_raw.csv (stažené z druhého Supabase projektu -
scrapnutá data z Daft.ie) do formátu připraveného pro staging tabulku
`daft_staging` v Supabase.

Čištění:
- price/sold_price: odstranění měnového symbolu (poškozený kódováním na
  zdroji, â‚¬) a čárek -> čisté číslo
- bedrooms/bathrooms: "3 Bed" / "1 Bath" -> celé číslo
- floor_area: JSON {"unit": "...", "value": "..."} -> číslo v m² (převod
  ze čtverečních stop, pokud je unit SQUARE_FEET)
- sold_date: dd/mm/yyyy -> ISO
- eircode: zkusí se vytáhnout z textu adresy/titulku regexem (Daft ho
  často uvádí přímo v titulku inzerátu)
"""
import os
import re
import json
import pandas as pd

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
SOURCE_CSV = os.path.join(RAW_DATA_DIR, "daft_raw.csv")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "daft_clean.csv")
CHUNK_SIZE = 50_000

EIRCODE_RE = re.compile(r"\b([AC-FHKNPRTV-Y]\d{2})\s?([AC-FHKNPRTV-Y0-9]{4})\b", re.IGNORECASE)

OUTPUT_COLUMNS = [
    "id", "url", "address", "eircode", "price", "sold_price", "sold_date",
    "bedrooms", "bathrooms", "property_type", "category", "listing_type",
    "floor_area_sqm", "date_of_construction", "area_name", "description",
    "scraped_at", "ber_code", "ber_rating", "latitude", "longitude",
]


def clean_money(value) -> str:
    if pd.isna(value):
        return ""
    cleaned = re.sub(r"[^\d.]", "", str(value))
    return cleaned


def extract_int(value) -> str:
    if pd.isna(value):
        return ""
    match = re.search(r"\d+", str(value))
    return match.group(0) if match else ""


def extract_eircode(title) -> str:
    if pd.isna(title):
        return ""
    match = EIRCODE_RE.search(str(title))
    if not match:
        return ""
    return f"{match.group(1)}{match.group(2)}".upper()


def normalize_address(title) -> str:
    if pd.isna(title):
        return ""
    return re.sub(r"\s+", " ", str(title)).strip().upper()


def parse_floor_area(value) -> str:
    if pd.isna(value) or not str(value).strip():
        return ""
    try:
        data = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    raw_value = data.get("value")
    unit = (data.get("unit") or "").upper()
    try:
        num = float(raw_value)
    except (TypeError, ValueError):
        return ""
    if num <= 0:
        return ""
    if "FEET" in unit or "FOOT" in unit:
        num = num * 0.09290304
    return str(round(num, 2))


def parse_sold_date(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, format="%d/%m/%Y", errors="coerce")
    return dt.dt.strftime("%Y-%m-%d").fillna("")


def main():
    if not os.path.exists(SOURCE_CSV):
        raise FileNotFoundError(f"Nenalezen {SOURCE_CSV}. Nejprve spusť download_daft.py")

    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)

    print(f"📄 Zpracovávám: {SOURCE_CSV}")
    total = 0
    first = True

    for chunk in pd.read_csv(SOURCE_CSV, chunksize=CHUNK_SIZE, dtype=str, on_bad_lines="skip"):
        total += len(chunk)

        out = pd.DataFrame({
            "id": chunk["id"],
            "url": chunk["url"],
            "address": chunk["title"].map(normalize_address),
            "eircode": chunk["title"].map(extract_eircode),
            "price": chunk["price"].map(clean_money),
            "sold_price": chunk["sold_price"].map(clean_money),
            "sold_date": parse_sold_date(chunk["sold_date"]),
            "bedrooms": chunk["bedrooms"].map(extract_int),
            "bathrooms": chunk["bathrooms"].map(extract_int),
            "property_type": chunk["property_type"].fillna(""),
            "category": chunk["category"].fillna(""),
            "listing_type": chunk["listing_type"].fillna(""),
            "floor_area_sqm": chunk["floor_area"].map(parse_floor_area),
            "date_of_construction": chunk["date_of_construction"].fillna(""),
            "area_name": chunk["area_name"].fillna(""),
            "description": chunk["description"].fillna(""),
            "scraped_at": chunk["scraped_at"].fillna(""),
            "ber_code": chunk["ber_code"].fillna(""),
            "ber_rating": chunk["ber_rating"].fillna(""),
            "latitude": chunk["latitude"].fillna(""),
            "longitude": chunk["longitude"].fillna(""),
        }, columns=OUTPUT_COLUMNS)

        out = out[out["id"].notna() & (out["id"].astype(str).str.strip() != "")]

        out.to_csv(OUTPUT_CSV, mode="a", header=first, index=False, encoding="utf-8")
        first = False
        print(f"  ↳ zpracováno {total}...")

    print(f"✅ Hotovo! {OUTPUT_CSV} připraveno k importu.")


if __name__ == "__main__":
    main()
