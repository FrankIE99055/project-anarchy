"""
load_ppr_to_db.py
------------------
Načte stažený CSV soubor z Property Price Register, vyčistí data
a nahraje je do Supabase (tabulky `properties` a `sales_history`).

Pro první testovací běh je import omezen na jeden county a rok (viz
konstanty níže), aby se ověřilo, že celá pipeline funguje, než pustíme
import celé irské databáze (miliony záznamů).

Výkon: nemovitosti i prodeje se nahrávají hromadně (bulk upsert/insert)
po dávkách místo jednoho HTTP requestu na každý řádek CSV. Vyžaduje
unikátní omezení na sloupcích `eircode` a `address` (viz
database_schema/02_add_address_unique.sql).
"""
import os
import glob
import re
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# ---- Konfigurace testovacího importu ----
FILTER_COUNTY = "Dublin"     # None = bez filtru (celá databáze)
FILTER_YEAR_FROM = 2023      # None = bez filtru
CHUNK_SIZE = 5000            # kolik řádků CSV se čte a zpracovává najednou
UPSERT_BATCH_SIZE = 500      # velikost dávky pro jeden HTTP request na Supabase

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")


def find_csv_file() -> str:
    csv_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            "Nenalezen žádný CSV v raw_data/. Nejprve spusť download_ppr.py"
        )
    return csv_files[0]


def normalize_columns(columns):
    return [re.sub(r"\s+", " ", c).strip().lower() for c in columns]


def clean_price(value: str) -> float | None:
    if pd.isna(value):
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value))
    return float(cleaned) if cleaned else None


def normalize_address(address: str) -> str:
    return re.sub(r"\s+", " ", str(address)).strip().upper()


def normalize_eircode(eircode) -> str | None:
    if eircode is None or pd.isna(eircode) or not str(eircode).strip():
        return None
    return str(eircode).strip().upper()


def batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def bulk_get_or_create_properties(rows: list[dict], cache: dict) -> None:
    """Zajistí, že všechny nemovitosti z `rows` mají záznam v Supabase a
    ID uložené v `cache` (klíč = eircode nebo normalizovaná adresa).

    Místo jednoho requestu na řádek se nemovitosti nahrávají hromadně
    pomocí `upsert` (on_conflict na eircode / address), což vrátí ID
    všech řádků v jednom volání.
    """
    with_eircode = {}
    without_eircode = {}

    for row in rows:
        eircode = normalize_eircode(row.get("eircode"))
        address_norm = normalize_address(row.get("address"))
        key = eircode or address_norm
        if key in cache:
            continue
        if eircode:
            with_eircode[eircode] = {"address": address_norm, "eircode": eircode}
        else:
            without_eircode[address_norm] = {"address": address_norm, "eircode": None}

    for batch in batched(list(with_eircode.values()), UPSERT_BATCH_SIZE):
        result = supabase.table("properties").upsert(batch, on_conflict="eircode").execute()
        for record in result.data:
            cache[record["eircode"]] = record["id"]

    for batch in batched(list(without_eircode.values()), UPSERT_BATCH_SIZE):
        result = supabase.table("properties").upsert(batch, on_conflict="address").execute()
        for record in result.data:
            cache[record["address"]] = record["id"]


def main():
    csv_path = find_csv_file()
    print(f"📄 Zpracovávám soubor: {csv_path}")

    property_cache: dict = {}
    total_rows = 0
    inserted_sales = 0

    for chunk in pd.read_csv(
        csv_path,
        chunksize=CHUNK_SIZE,
        encoding="cp1252",
        dtype=str,
        on_bad_lines="skip",
    ):
        chunk.columns = normalize_columns(chunk.columns)
        total_rows += len(chunk)

        # Sloupce v PPR CSV: "date of sale (dd/mm/yyyy)", "address",
        # "county", "price (€)", "description of property", ...
        date_col = next((c for c in chunk.columns if "date of sale" in c), None)
        county_col = next((c for c in chunk.columns if c == "county"), None)
        eircode_col = next((c for c in chunk.columns if c == "eircode"), None)
        price_col = next((c for c in chunk.columns if "price" in c), None)
        desc_col = next((c for c in chunk.columns if "description of property" in c), None)

        if FILTER_COUNTY and county_col:
            chunk = chunk[chunk[county_col].str.strip().str.lower() == FILTER_COUNTY.lower()]

        if FILTER_YEAR_FROM and date_col:
            parsed_dates = pd.to_datetime(chunk[date_col], format="%d/%m/%Y", errors="coerce")
            chunk = chunk[parsed_dates.dt.year >= FILTER_YEAR_FROM]
            parsed_dates = parsed_dates[chunk.index]
        else:
            parsed_dates = pd.to_datetime(chunk[date_col], format="%d/%m/%Y", errors="coerce")

        if chunk.empty:
            continue

        # Nejdřív hromadně zajistíme všechny nemovitosti z tohoto chunku
        # (pár desítek requestů místo tisíců).
        raw_rows = [
            {"address": row.get("address"), "eircode": row.get(eircode_col) if eircode_col else None}
            for _, row in chunk.iterrows()
            if row.get("address") and not pd.isna(row.get("address"))
        ]
        bulk_get_or_create_properties(raw_rows, property_cache)

        sales_batch = []
        for idx, row in chunk.iterrows():
            address = row.get("address")
            if not address or pd.isna(address):
                continue

            eircode = normalize_eircode(row.get(eircode_col) if eircode_col else None)
            key = eircode or normalize_address(address)
            property_id = property_cache.get(key)
            if property_id is None:
                continue

            sale_date = parsed_dates.loc[idx]
            price = clean_price(row.get(price_col)) if price_col else None

            sales_batch.append(
                {
                    "property_id": property_id,
                    "date_of_sale": sale_date.date().isoformat() if pd.notna(sale_date) else None,
                    "price": price,
                    "description": row.get(desc_col) if desc_col else None,
                }
            )

        for batch in batched(sales_batch, UPSERT_BATCH_SIZE):
            supabase.table("sales_history").insert(batch).execute()
            inserted_sales += len(batch)
        if sales_batch:
            print(f"  ↳ Nahráno {inserted_sales} záznamů prodejů (zpracováno {total_rows} řádků CSV)...")

    print(f"✅ Hotovo! Celkem zpracováno {total_rows} řádků, nahráno {inserted_sales} prodejů "
          f"a {len(property_cache)} unikátních nemovitostí.")


if __name__ == "__main__":
    main()

