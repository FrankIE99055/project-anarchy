"""
download_osm_addresses.py
--------------------------
Stáhne extrakt OpenStreetMap dat pro Irsko + Severní Irsko z Geofabrik
(.osm.pbf, ~390 MB, aktualizováno denně) a vytáhne z něj VŠECHNY body/
budovy s libovolným adresním tagem (housenumber/street/city/postcode) -
nejen ty s Eircode. Eircode se doplní tam, kde je k dispozici; jinde
zůstane prázdný (adresa bez Eircode je pořád adresa, kterou chceme mít
v DB kvůli párování budoucích planning/Daft signálů).

DŮLEŽITÉ (přesnost dat): Eircode/adresa v OSM je dobrovolnický údaj
(mapéři ho ručně opsali), NE autoritativní zdroj jako GeoDirectory/An
Post. Bereme to jako DOPLŇKOVÝ zdroj GPS + adres (lepší než townland-
centroid aproximace, protože jde o skutečný bod domu/budovy), ne jako
nahrazení existujícího párování (Daft eircode, townland gazetteer).

GDPR: OSM adresní tagy (addr:housenumber/addr:street/addr:city/
addr:postcode) se váží na MÍSTO/budovu, ne na osobu - žádné osobní údaje
se nestahují ani neukládají (stejná politika jako u ostatních zdrojů v
tomhle projektu).

VYŘAZENÍ SEVERNÍHO IRSKA: extrakt pokrývá Irsko I Severní Irsko
dohromady (Geofabrik je nemá zvlášť). Vyřazujeme podle:
  1) addr:country tagu, pokud říká GB/UK,
  2) PSČ začínajícího na 'BT' (Belfast postcode area pokrývá VŠECHNA
     severoirská PSČ - spolehlivý signál),
  3) obecného formátu britského PSČ (pro případ, že by šlo o jiný NI
     postcode prefix, který jsme nezachytili výše).
Adresy BEZ jakéhokoli PSČ/country tagu se ponechají (nemáme signál, že
jsou z NI, a naprostá většina takových je z RoI).

Použití:
    pip install pyrosm  (už je v .venv nainstalováno)
    python download_osm_addresses.py

Výstup: raw_data/osm_addresses_raw.csv (sloupec eircode může být prázdný)
"""
import os
import re
import sys
import threading
import time

import requests

# Windows: stdout se při přesměrování do souboru/pipe defaultně kóduje podle
# konzolové codepage (cp1250 apod.), což spadne na emoji/české znaky níže.
# Vynutit UTF-8 bez ohledu na to, jak je skript spuštěný.
sys.stdout.reconfigure(encoding="utf-8")


def _heartbeat(stop_event: threading.Event, label: str):
    """Vypíše '... stále běží' každých 10s, dokud běží dlouhá operační
    (pyrosm nemá vlastní progress hook) - aby bylo v terminu vidět životně,
    že proces žije a nezasekl se, ne jen ticho na několik minut."""
    start = time.time()
    while not stop_event.wait(10):
        print(f"  ⏳ {label}... {time.time() - start:.0f}s", flush=True)


def _run_with_heartbeat(label: str, fn, *args, **kwargs):
    stop_event = threading.Event()
    hb = threading.Thread(target=_heartbeat, args=(stop_event, label), daemon=True)
    hb.start()
    try:
        return fn(*args, **kwargs)
    finally:
        stop_event.set()
        hb.join()


RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
PBF_PATH = os.path.join(RAW_DATA_DIR, "ireland-and-northern-ireland-latest.osm.pbf")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "osm_addresses_raw.csv")

PBF_URL = "https://download.geofabrik.de/europe/ireland-and-northern-ireland-latest.osm.pbf"

# Routing key (1 písmeno + 2 číslice) + mezera (volitelná) + 4 alfanumerické
# znaky unique identifier - viz https://www.eircode.ie
EIRCODE_RE = re.compile(r"^([A-Za-z]\d{2})\s?([A-Za-z0-9]{4})$")

# Obecný formát britského PSČ (pokrývá i severoirské mimo 'BT', pro jistotu)
UK_POSTCODE_RE = re.compile(r"^[A-Za-z]{1,2}\d[A-Za-z0-9]?\s?\d[A-Za-z]{2}$")


def download_pbf():
    if os.path.exists(PBF_PATH):
        print(f"✅ {PBF_PATH} už existuje, přeskakuji stahování.")
        return
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    print(f"📡 Stahuji {PBF_URL} ...")
    with requests.get(PBF_URL, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        written = 0
        with open(PBF_PATH, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                written += len(chunk)
                if total:
                    print(f"  ↳ {written / 1_000_000:.0f} / {total / 1_000_000:.0f} MB", end="\r")
    print(f"\n✅ Staženo: {PBF_PATH}")


def normalize_eircode(raw: str) -> str | None:
    """Vrátí Eircode ve formátu 'XXX XXXX' pokud `raw` vypadá jako platný
    irský Eircode (routing key + unique identifier), jinak None."""
    if not raw:
        return None
    compact = raw.strip().upper().replace(" ", "")
    if len(compact) != 7:
        return None
    if not EIRCODE_RE.match(f"{compact[:3]} {compact[3:]}"):
        return None
    return f"{compact[:3]} {compact[3:]}"


def is_northern_ireland(country: str | None, postcode: str | None) -> bool:
    """Heuristika pro vyřazení severoirských adres (viz hlavička modulu)."""
    if country and country.strip().upper() in ("GB", "UK", "UNITED KINGDOM", "NORTHERN IRELAND"):
        return True
    if postcode:
        compact = postcode.strip().upper().replace(" ", "")
        if compact.startswith("BT"):
            return True
        if UK_POSTCODE_RE.match(postcode.strip()) and not normalize_eircode(postcode):
            return True
    return False


def extract_addresses():
    from pyrosm import OSM

    print("📖 Načítám OSM extrakt (může to chvíli trvat)...", flush=True)
    osm = _run_with_heartbeat("Parsuji .osm.pbf", OSM, PBF_PATH)

    # Širší filtr - VŠECHNY prvky s JAKÝMKOLIV adresním tagem (ne jen ty s
    # Eircode). Eircode/NI kontrolu děláme až v Pythonu.
    custom_filter = {
        "addr:housenumber": True,
        "addr:street": True,
        "addr:city": True,
        "addr:postcode": True,
        "addr:eircode": True,
    }
    print("🔍 Filtruji prvky s adresním tagem...", flush=True)
    gdf = _run_with_heartbeat(
        "Filtruji adresy",
        osm.get_data_by_custom_criteria,
        custom_filter=custom_filter,
        filter_type="keep",
        keep_nodes=True,
        keep_ways=True,
        keep_relations=False,
    )
    print(f"📦 Nalezeno {len(gdf)} prvků s adresním tagem (Irsko + Severní Irsko dohromady).", flush=True)

    rows = []
    skipped_ni = 0
    total = len(gdf)
    for i, (_, r) in enumerate(gdf.iterrows()):
        if i and i % 50_000 == 0:
            print(f"  ↳ zpracováno {i}/{total} ({i * 100 // total}%)...", flush=True)
        housenumber = r.get("addr:housenumber")
        street = r.get("addr:street")
        city = r.get("addr:city") or r.get("addr:town")
        postcode_raw = r.get("addr:eircode") or r.get("addr:postcode")
        country = r.get("addr:country")

        if not (housenumber or street or city):
            continue  # nic použitelného jako adresa

        if is_northern_ireland(country, postcode_raw if isinstance(postcode_raw, str) else None):
            skipped_ni += 1
            continue

        eircode = normalize_eircode(postcode_raw) if isinstance(postcode_raw, str) else None

        geom = r.get("geometry")
        if geom is None:
            continue
        centroid = geom.centroid
        rows.append(
            {
                "eircode": eircode,
                "housenumber": housenumber,
                "street": street,
                "city": city,
                "longitude": centroid.x,
                "latitude": centroid.y,
            }
        )

    print(f"🚫 Vyřazeno jako Severní Irsko: {skipped_ni}")
    print(f"✅ {len(rows)} adres v Irské republice (s Eircode i bez).")

    import pandas as pd

    df = pd.DataFrame(rows)
    before = len(df)
    df = df.drop_duplicates(subset=["eircode", "housenumber", "street", "city"])
    print(f"📉 Po deduplikaci: {len(df)} řádků (z {before}).")
    with_eircode = df["eircode"].notna().sum()
    print(f"   ↳ z toho {with_eircode} s Eircode, {len(df) - with_eircode} bez Eircode.")
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"✅ Hotovo! {OUTPUT_CSV}")


if __name__ == "__main__":
    download_pbf()
    extract_addresses()
