"""
build_duplicate_photo_export.py
---------------------------------
Na žádost uživatele: exportuje nemovitosti, které jsou zároveň na
Derelict/Vacant registru A mají odpovídající Daft.ie inzerát, včetně
fotek z Daft.ie (pokud je pro daný inzerát scraper zachytil - ne všechny
inzeráty mají fotky, `images`/`media.images` bývá u části záznamů
prázdné).

Fotky NEJSOU v naší vlastní `daft_listings` tabulce (viz download_daft.py -
`media`/`images`/`photo_urls` byly při importu záměrně vynechány, aby CSV
zůstalo štíhlé) - musí se dotáhnout přímo ze zdrojového Daft Supabase
projektu (DAFT_SUPABASE_URL/KEY).

Výstup: raw_data/duplicate_photo_raw.csv (property_id, address, eircode,
propensity_score, key_drivers, daft_id, daft_url, photo_urls - photo_urls
je '|'-oddělený seznam URL, prázdné pokud inzerát nemá fotky).
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv
from supabase import create_client

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DAFT_SOURCE_URL = os.environ["DAFT_SUPABASE_URL"].rstrip("/")
DAFT_SOURCE_KEY = os.environ["DAFT_SUPABASE_KEY"]

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "duplicate_photo_raw.csv")


def fetch_derelict_daft_properties() -> list[dict]:
    """Nemovitosti na derelict registru, které mají i property_id shodu s
    Daft.ie (property + jeden reprezentativní daft_listings řádek)."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    derelict = (
        supabase.table("derelict_sites")
        .select("property_id")
        .not_.is_("property_id", "null")
        .execute()
    ).data
    property_ids = sorted({r["property_id"] for r in derelict})
    print(f"📋 {len(property_ids)} unikátních nemovitostí na derelict registru.")

    rows = []
    CHUNK = 200
    for i in range(0, len(property_ids), CHUNK):
        chunk = property_ids[i : i + CHUNK]
        props = (
            supabase.table("properties")
            .select("id,address,eircode,propensity_score,key_drivers")
            .in_("id", chunk)
            .execute()
        ).data
        daft = (
            supabase.table("daft_listings")
            .select("id,property_id,url")
            .in_("property_id", chunk)
            .execute()
        ).data
        daft_by_property = {}
        for d in daft:
            daft_by_property.setdefault(d["property_id"], d)  # jeden zástupce na property

        for p in props:
            d = daft_by_property.get(p["id"])
            if not d:
                continue
            rows.append(
                {
                    "property_id": p["id"],
                    "address": p["address"],
                    "eircode": p.get("eircode"),
                    "propensity_score": p.get("propensity_score"),
                    "key_drivers": "; ".join(p.get("key_drivers") or []),
                    "daft_id": d["id"],
                    "daft_url": d.get("url"),
                }
            )
    print(f"✅ {len(rows)} nemovitostí má property + Daft shodu.")
    return rows


def fetch_photo_urls(daft_ids: list[int]) -> dict[int, list[str]]:
    """Dotáhne fotky ze ZDROJOVÉHO Daft Supabase projektu pro dané ID.
    Vrací {daft_id: [url, ...]} - prázdný seznam, pokud inzerát fotky nemá."""
    headers = {"apikey": DAFT_SOURCE_KEY, "Authorization": f"Bearer {DAFT_SOURCE_KEY}"}
    result: dict[int, list[str]] = {}

    CHUNK = 50
    for i in range(0, len(daft_ids), CHUNK):
        chunk = daft_ids[i : i + CHUNK]
        id_list = ",".join(str(x) for x in chunk)
        resp = requests.get(
            f"{DAFT_SOURCE_URL}/rest/v1/properties",
            headers=headers,
            params={"select": "id,images", "id": f"in.({id_list})"},
            timeout=60,
        )
        resp.raise_for_status()
        for row in resp.json():
            urls = []
            for entry in row.get("images") or []:
                entry_urls = entry.get("urls") or []
                if entry_urls:
                    urls.append(entry_urls[-1])  # poslední bývá nejvyšší rozlišení
            result[row["id"]] = urls
        print(f"  ↳ fotky zjištěny pro {min(i + CHUNK, len(daft_ids))}/{len(daft_ids)} inzerátů...")

    return result


def main():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    rows = fetch_derelict_daft_properties()
    if not rows:
        print("⚠️ Žádné nemovitosti k exportu.")
        return

    daft_ids = [r["daft_id"] for r in rows]
    photo_map = fetch_photo_urls(daft_ids)

    with_photos = sum(1 for d in daft_ids if photo_map.get(d))
    print(f"📸 {with_photos}/{len(daft_ids)} inzerátů má aspoň jednu fotku.")

    import csv

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "property_id", "address", "eircode", "propensity_score",
                "key_drivers", "daft_id", "daft_url", "photo_urls",
            ],
        )
        writer.writeheader()
        for r in rows:
            urls = photo_map.get(r["daft_id"], [])
            writer.writerow({**r, "photo_urls": "|".join(urls)})

    print(f"✅ Hotovo! {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
