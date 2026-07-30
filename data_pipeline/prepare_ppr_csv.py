"""
prepare_ppr_csv.py
-------------------
Připraví CSV z Property Price Register pro PŘÍMÝ import do Supabase
(bez Python skriptu volajícího API řádek po řádku).

Z raw_data/PPR-ALL.csv (encoding cp1252, formát PSRA) vyrobí
raw_data/ppr_clean.csv s vyčištěnými sloupci připravenými pro COPY/CSV
import do staging tabulky v Postgresu:

    date_of_sale (YYYY-MM-DD), address, county, eircode, price, description

Postup použití:
1. Spustit tento skript -> vznikne raw_data/ppr_clean.csv
2. V Supabase spustit database_schema/03_staging_and_bulk_load.sql
   (vytvoří prázdnou staging tabulku `ppr_staging`)
3. V Supabase Table Editoru -> tabulka `ppr_staging` -> Insert -> Import
   data from CSV -> nahrát ppr_clean.csv
4. Spustit zbytek SQL v 03_staging_and_bulk_load.sql (naplní properties
   a sales_history jedním hromadným INSERT ... SELECT, žádné API volání)
"""
import os
import re
import pandas as pd

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
SOURCE_CSV = os.path.join(RAW_DATA_DIR, "PPR-ALL.csv")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "ppr_clean.csv")
CHUNK_SIZE = 50_000

OUTPUT_COLUMNS = ["date_of_sale", "address", "county", "eircode", "price", "description"]


def normalize_columns(columns):
    return [re.sub(r"\s+", " ", c).strip().lower() for c in columns]


def clean_price(value) -> str:
    if pd.isna(value):
        return ""
    cleaned = re.sub(r"[^\d.]", "", str(value))
    return cleaned


def normalize_address(address) -> str:
    if pd.isna(address):
        return ""
    return re.sub(r"\s+", " ", str(address)).strip().upper()


def normalize_eircode(eircode) -> str:
    if pd.isna(eircode) or not str(eircode).strip():
        return ""
    return str(eircode).strip().upper()


def main():
    if not os.path.exists(SOURCE_CSV):
        raise FileNotFoundError(
            f"Nenalezen {SOURCE_CSV}. Nejprve spusť download_ppr.py"
        )

    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)

    print(f"📄 Zpracovávám: {SOURCE_CSV}")
    total_rows = 0
    written_rows = 0
    first_chunk = True

    for chunk in pd.read_csv(
        SOURCE_CSV,
        chunksize=CHUNK_SIZE,
        encoding="cp1252",
        dtype=str,
        on_bad_lines="skip",
    ):
        chunk.columns = normalize_columns(chunk.columns)
        total_rows += len(chunk)

        date_col = next((c for c in chunk.columns if "date of sale" in c), None)
        county_col = next((c for c in chunk.columns if c == "county"), None)
        eircode_col = next((c for c in chunk.columns if c == "eircode"), None)
        price_col = next((c for c in chunk.columns if "price" in c), None)
        desc_col = next((c for c in chunk.columns if "description of property" in c), None)
        address_col = next((c for c in chunk.columns if c == "address"), None)

        chunk = chunk[chunk[address_col].notna() & (chunk[address_col].str.strip() != "")]
        if chunk.empty:
            continue

        parsed_dates = pd.to_datetime(chunk[date_col], format="%d/%m/%Y", errors="coerce")

        out = pd.DataFrame({
            "date_of_sale": parsed_dates.dt.strftime("%Y-%m-%d").fillna(""),
            "address": chunk[address_col].map(normalize_address),
            "county": chunk[county_col].fillna("") if county_col else "",
            "eircode": chunk[eircode_col].map(normalize_eircode) if eircode_col else "",
            "price": chunk[price_col].map(clean_price) if price_col else "",
            "description": chunk[desc_col].fillna("") if desc_col else "",
        }, columns=OUTPUT_COLUMNS)

        out.to_csv(
            OUTPUT_CSV,
            mode="a",
            header=first_chunk,
            index=False,
            encoding="utf-8",
        )
        first_chunk = False
        written_rows += len(out)
        print(f"  ↳ zpracováno {total_rows} řádků, zapsáno {written_rows}...")

    print(f"✅ Hotovo! {OUTPUT_CSV} obsahuje {written_rows} řádků, připraveno k importu.")


if __name__ == "__main__":
    main()
