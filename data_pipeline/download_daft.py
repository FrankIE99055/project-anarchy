"""
download_daft.py
------------------
Stáhne kompletní scrapnutý dataset z Daft.ie z DRUHÉHO Supabase projektu
uživatele (tabulka `properties`) a uloží ho lokálně jako CSV.

Nemáme heslo k té databázi (jen anon klíč), takže pg_dump nejde použít -
stahujeme přes REST API po stránkách (keyset pagination podle `id`, což
je rychlejší a spolehlivější než OFFSET/LIMIT u velkých tabulek).

Zdroj: DAFT_SUPABASE_URL / DAFT_SUPABASE_KEY v .env
"""
import os
import csv
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
SOURCE_URL = os.environ["DAFT_SUPABASE_URL"].rstrip("/")
SOURCE_KEY = os.environ["DAFT_SUPABASE_KEY"]

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "daft_raw.csv")
PAGE_SIZE = 1000

# Jen pole, která reálně využijeme - vynecháváme velké/redundantní JSON
# blob sloupce (raw_listing, media, images, photo_urls, sections, features).
SELECT_FIELDS = (
    "id,url,title,price,sold_price,sold_date,bedrooms,bathrooms,"
    "property_type,category,listing_type,floor_area,date_of_construction,"
    "area_name,description,scraped_at,ber,location"
)

OUTPUT_COLUMNS = [
    "id", "url", "title", "price", "sold_price", "sold_date", "bedrooms",
    "bathrooms", "property_type", "category", "listing_type", "floor_area",
    "date_of_construction", "area_name", "description", "scraped_at",
    "ber_code", "ber_rating", "latitude", "longitude",
]


def fetch_page(last_id: int) -> list[dict]:
    headers = {
        "apikey": SOURCE_KEY,
        "Authorization": f"Bearer {SOURCE_KEY}",
    }
    params = {
        "select": SELECT_FIELDS,
        "id": f"gt.{last_id}",
        "order": "id.asc",
        "limit": str(PAGE_SIZE),
    }
    for attempt in range(3):
        try:
            resp = requests.get(
                f"{SOURCE_URL}/rest/v1/properties",
                headers=headers,
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  ⚠️ chyba, zkouším znovu ({e})")
            time.sleep(2)


def flatten(row: dict) -> dict:
    ber = row.get("ber") or {}
    location = row.get("location") or {}
    return {
        "id": row.get("id"),
        "url": row.get("url"),
        "title": row.get("title"),
        "price": row.get("price"),
        "sold_price": row.get("sold_price"),
        "sold_date": row.get("sold_date"),
        "bedrooms": row.get("bedrooms"),
        "bathrooms": row.get("bathrooms"),
        "property_type": row.get("property_type"),
        "category": row.get("category"),
        "listing_type": row.get("listing_type"),
        "floor_area": row.get("floor_area"),
        "date_of_construction": row.get("date_of_construction"),
        "area_name": row.get("area_name"),
        "description": row.get("description"),
        "scraped_at": row.get("scraped_at"),
        "ber_code": ber.get("code"),
        "ber_rating": ber.get("rating"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
    }


def main():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    last_id = 0
    total = 0

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        while True:
            rows = fetch_page(last_id)
            if not rows:
                break
            for row in rows:
                writer.writerow(flatten(row))
            total += len(rows)
            last_id = rows[-1]["id"]
            print(f"  ↳ staženo {total}...")
            if len(rows) < PAGE_SIZE:
                break

    print(f"✅ Hotovo! {OUTPUT_CSV} obsahuje {total} záznamů.")


if __name__ == "__main__":
    main()
