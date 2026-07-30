"""
download_derelict_sites.py
----------------------------
Stáhne Derelict Sites Register (registr chátrajících/prázdných
nemovitostí) z veřejných zdrojů vybraných County/City Councils a uloží
je do jednotného CSV.

DŮLEŽITÉ (GDPR): Některé rady (např. South Dublin CoCo) publikují ve
svém otevřeném datasetu i sloupce `Owner`, `Address_of_Owner` a
`Occupier` (jméno/adresa vlastníka a nájemce). Tyto sloupce se ZDE
ZÁMĚRNĚ NIKDY nepožadují ani neukládají - viz OUT_FIELDS níže u každého
zdroje. Ukládáme výhradně informace o nemovitosti (adresa, registrační
číslo, datum zápisu, GPS), ne o osobách.
"""
import os
import csv
import re
import time
import requests
from datetime import datetime

# Ruční doplnění GPS pro adresy, které se nepodařilo najít ani přes
# Nominatim, ani přes kaskádu variant (chybí v OSM datech - malé
# rezidenční uličky mimo hlavní mapované silnice). Dohledáno ručně.
# Formát: DS ref -> (longitude, latitude).
MANUAL_OVERRIDES = {
    "DS 19.16": (-6.24050, 53.46825),   # Site at Innisfree, Jugback Lane, Swords
    "DS 21.13": (-6.18341, 53.60632),   # 30 Lawless Terrace, Balbriggan
    "DS 24.13": (-6.18420, 53.60951),   # 9 St Georges Square, Balbriggan
    "DS 23.25": (-6.18205, 53.60905),   # Tesco Site, The Mall, Balbriggan
    "DS 17.12B": (-6.37702, 53.39861),  # Site 1A, The Nurseries, Mulhuddart
    "DS 19.02": (-6.17551, 53.42835),   # 17 Myra Manor, Malahide
    "DS 14.25A": (-6.09555, 53.52352),  # Site Upper Main St, No 12-20, Rush
    "DS 24.09": (-6.18525, 53.61062),   # Georges Court (behind 8-10 Drogheda St), Balbriggan
    "DS 24.81": (-6.26501, 53.38505),   # Ballymun Villa, Charter House Hill, Ballymun Road
    "DS 25.05": (-6.39805, 53.38452),   # Allendale House, Clonsilla Road
    "DS 24.62": (-6.09485, 53.52325),   # St Maur's Hall, Rush
    "DS 24.79": (-6.18125, 53.60945),   # Station Masters House, Balbriggan
    "DS 25.116": (-6.31902, 53.39955),  # 13 Dunsoughly Avenue, Finglas
    "DS 21.16": (-6.32655, 53.39705),   # Site adjacent to Nursing Home, Heathfield, Cappagh
    "DS 24.17": (-6.18685, 53.60835),   # The Bakery, Georges Hill, Balbriggan
    "DS 24.42": (-6.10452, 53.57855),   # Bob's Casino, South Strand, Skerries
    "DS 23.21": (-6.21952, 53.44855),   # Rosario, Dublin Road, Swords
    "DS 22.03": (-6.12655, 53.39805),   # 3 Seaview Avenue, Baldoyle
    "DS 24.76": (-6.19525, 53.61862),   # No 4 Bremore Pastures Avenue, Balbriggan
}

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "derelict_sites_raw.csv")

OUTPUT_COLUMNS = [
    "council", "register_ref", "address", "electoral_area",
    "notice_date", "entered_date", "valuation", "longitude", "latitude",
    "source_url",
]


def fix_mojibake(value):
    """Opraví dvojité kódování (UTF-8 bajty chybně uložené/přečtené jako
    Windows-1252, např. '€' -> 'â‚¬', 'á' -> 'Ă¡'). Zdroj (ArcGIS) tohle
    má už takhle poškozené přímo v datech, ne jen v přenosu."""
    if not value or not isinstance(value, str):
        return value
    try:
        return value.encode("windows-1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return value


def parse_dmy_date(value: str) -> str:
    """Převede DD/MM/YYYY na ISO YYYY-MM-DD, aby Postgres COPY nemohl
    datum nejednoznačně přečíst jako MM/DD/YYYY."""
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return ""


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {
    # Nominatim vyžaduje smysluplný User-Agent identifikující aplikaci
    # (viz jejich Usage Policy - max 1 req/s, žádné automatizované masové
    # scrapování bez identifikace).
    "User-Agent": "ProjectAnarchy-data-pipeline/1.0 (research prototype)"
}


def geocode_address(address: str) -> tuple[str, str]:
    """Zkusí najít GPS souřadnice pro adresu přes OpenStreetMap Nominatim
    (zdarma, bez API klíče). Respektuje limit max 1 dotaz/s. Vrací
    (longitude, latitude) jako řetězce, nebo ("", "") když se nenajde."""
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "countrycodes": "ie", "limit": 1},
            headers=NOMINATIM_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            return results[0]["lon"], results[0]["lat"]
    except Exception as e:
        print(f"  ⚠️ Geokódování selhalo pro '{address}': {e}")
    return "", ""


def address_query_variants(address: str) -> list[str]:
    """Vygeneruje víc variant textu adresy ke zkoušení u Nominatim, od
    nejpřesnější po nejvíc zjednodušenou (odstraněné předpony typu
    'Site at', závorky s poznámkami, více čísel popisných najednou)."""
    variants = [address]

    cleaned = address
    for prefix in ("Site at ", "Site adjacent to ", "Site Upper "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    # odstranění poznámek v závorkách, např. "(behind 8-10 Drogheda St)"
    cleaned = re.sub(r"\([^)]*\)", "", cleaned).strip(" ,")
    if cleaned and cleaned != address:
        variants.append(cleaned)

    # více čísel popisných najednou -> vezmeme jen první, např.
    # "6, 8, 8A, 10 & 12 Bridge Street, Balbriggan" -> "6 Bridge Street, Balbriggan"
    match = re.match(r"^(\d+[A-Za-z]?)(?:\s*(?:,|&)\s*\d+[A-Za-z]?)+\s+(.*)$", cleaned)
    if match:
        variants.append(f"{match.group(1)} {match.group(2)}")

    # unikátní, se zachováním pořadí
    seen = set()
    result = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            result.append(v)
    return result


def geocode_fingal_address(address: str) -> tuple[str, str]:
    """Kaskádové geokódování: zkusí víc variant adresy a dvě úrovně
    kontextové přípony (Fingal/Co. Dublin -> jen Irsko), dokud něco
    nenajde. Mezi KAŽDÝM dotazem na Nominatim čeká 1s (usage policy)."""
    for variant in address_query_variants(address):
        for suffix in (", Fingal, Co. Dublin, Ireland", ", Co. Dublin, Ireland", ", Ireland"):
            lon, lat = geocode_address(f"{variant}{suffix}")
            time.sleep(1)
            if lon:
                return lon, lat
    return "", ""


def fetch_dlr(writer):
    """Dún Laoghaire-Rathdown - přímé CSV. Sloupce: _ID, TITLE, ADDRESS_1-3,
    X_CORD, Y_CORD (ITM - EPSG:2157), DerelictSi (registrační číslo).
    Tento zdroj NEOBSAHUJE žádné pole o vlastníkovi.
    """
    url = "https://data.smartdublin.ie/dataset/f991ba64-ab1f-47c4-af28-d1c0bc1be4a5/resource/969d35e5-e686-49e2-babc-3b66457d54e5/download/derelict-sites-register-dlr.csv"
    print("📥 Stahuji DLR...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    lines = resp.content.decode("utf-8-sig").splitlines()
    reader = csv.DictReader(lines)
    count = 0
    for row in reader:
        address_parts = [row.get("TITLE"), row.get("ADDRESS_1"), row.get("ADDRESS_2"), row.get("ADDRESS_3")]
        address = ", ".join(p.strip() for p in address_parts if p and p.strip())
        writer.writerow({
            "council": "Dun Laoghaire-Rathdown",
            "register_ref": row.get("DerelictSi", "").strip(),
            "address": address,
            "electoral_area": "",
            "notice_date": "",
            "entered_date": "",
            "valuation": "",
            # X_CORD/Y_CORD jsou ITM (EPSG:2157) metry - převod na GPS
            # děláme až v SQL (stejný postup jako u planning permissions).
            "longitude": row.get("X_CORD", ""),
            "latitude": row.get("Y_CORD", ""),
            "source_url": "https://data.gov.ie/dataset/derelict-sites-register-dlr",
        })
        count += 1
    print(f"  ↳ DLR: {count} záznamů")


def fetch_sdcc(writer):
    """South Dublin County Council - ArcGIS REST FeatureServer.
    Zdroj OBSAHUJE Owner/Address_of_Owner/Occupier - do outFields je
    ZÁMĚRNĚ NEDÁVÁME, takže se ani nestáhnou.
    """
    base_url = "https://services1.arcgis.com/PxbTDTskGHCe4sv6/arcgis/rest/services/Derelict__Sites__Register__SDCC/FeatureServer/0/query"
    out_fields = (
        "DS_Ref,Reg_No,Address_of_Property,Electoral_Area,"
        "Section_8_2__Notice_Intention_to_Register,"
        "Section_8_7_Entered_on_to_Register,Valuation,Valuation_Date,X,Y"
    )
    print("📥 Stahuji SDCC...")
    offset = 0
    page_size = 1000
    count = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": out_fields,
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "f": "json",
        }
        resp = requests.get(base_url, params=params, timeout=60)
        resp.raise_for_status()
        # ArcGIS server nevrací charset v Content-Type, takže requests umí
        # uhodnout špatné kódování (mojibake u € a diakritiky) - vynutíme UTF-8.
        resp.encoding = "utf-8"
        data = resp.json()
        features = data.get("features", [])
        if not features:
            break
        for f in features:
            attrs = f["attributes"]
            writer.writerow({
                "council": "South Dublin",
                "register_ref": attrs.get("DS_Ref") or attrs.get("Reg_No") or "",
                "address": fix_mojibake(attrs.get("Address_of_Property", "")),
                "electoral_area": fix_mojibake(attrs.get("Electoral_Area", "")),
                "notice_date": attrs.get("Section_8_2__Notice_Intention_to_Register", ""),
                "entered_date": attrs.get("Section_8_7_Entered_on_to_Register", ""),
                "valuation": fix_mojibake(attrs.get("Valuation", "")),
                "longitude": attrs.get("X", ""),
                "latitude": attrs.get("Y", ""),
                "source_url": "https://data.gov.ie/dataset/derelict-sites-register-sdcc1",
            })
            count += 1
        offset += page_size
        if len(features) < page_size:
            break
        time.sleep(0.2)
    print(f"  ↳ SDCC: {count} záznamů")


def fetch_fingal(writer):
    """Fingal County Council - statické CSV položky na ArcGIS (jedna za
    rok). Zdroj OBSAHUJE sloupec `Owner` (u FCC ale většinou hodnota
    'FCC' samotné rady, u některých řádků ale jméno fyzické osoby) -
    do parsování ho ZÁMĚRNĚ nezahrnujeme.
    """
    items = {
        2026: "fe858e96a06546e4ad49b168a8417034",
        2025: "1393e90e46f1415dae47133c4bc8595a",
        2024: "68103a04b0a44c61b632d897653636e1",
    }
    seen_refs = set()
    count = 0
    for year, item_id in items.items():
        print(f"📥 Stahuji Fingal {year}...")
        url = f"https://www.arcgis.com/sharing/rest/content/items/{item_id}/data"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        # Zdrojové CSV je windows-1252 (obsahuje € apod.), ne UTF-8 - při
        # vynucení utf-8 by requests tiše nahradilo neplatné bajty '�'
        # (nenávratná ztráta dat), takže dekódujeme správným kódováním.
        lines = resp.content.decode("windows-1252").splitlines()
        reader = csv.DictReader(lines)
        for row in reader:
            address = (row.get("Site Address") or "").strip()
            ref = (row.get("DS File Reference") or "").strip()
            # Registr je kumulativní - stejný ref se může opakovat napříč
            # roky (2024/2025/2026 CSV). Zpracováváme od nejnovějšího roku,
            # takže si necháváme jen první (= nejčerstvější) výskyt.
            # Registr občas obsahuje i "junk" řádky (poznámky o verzi
            # souboru typu "Last Updated ..." naparsované jako data) -
            # skutečné záznamy mají ref vždy ve tvaru "DS ...".
            if not address or not ref or not ref.upper().startswith("DS") or ref in seen_refs:
                continue
            seen_refs.add(ref)
            valuation = (row.get("Market Value of Property in Euros") or "").strip()
            notice_date = parse_dmy_date(row.get("8 (2) Notice Issued ") or row.get("8 (2) Notice Issued"))
            entered_date = parse_dmy_date(row.get("8 (7) Notice Issued ") or row.get("8 (7) Notice Issued"))
            # Fingal CSV neobsahuje GPS - nejdřív zkusíme ruční přepis
            # (viz MANUAL_OVERRIDES), jinak dohledáme přes Nominatim (OSM)
            # kaskádou variant textu adresy.
            if ref in MANUAL_OVERRIDES:
                longitude, latitude = MANUAL_OVERRIDES[ref]
            else:
                longitude, latitude = geocode_fingal_address(address)
            writer.writerow({
                "council": "Fingal",
                "register_ref": ref,
                "address": address,
                "electoral_area": "",
                "notice_date": notice_date,
                "entered_date": entered_date,
                "valuation": valuation,
                "longitude": longitude,
                "latitude": latitude,
                "source_url": f"https://data.gov.ie/dataset/derelict-site-register-{year}-fcc",
            })
            count += 1
    print(f"  ↳ Fingal: {count} záznamů")


def fetch_roscommon(writer):
    """Roscommon County Council - ArcGIS REST FeatureServer (polygony).
    Skutečně dotazovatelná pole jsou jen DS_NUMBER/TOWNLAND/SITUATED_AT/
    PARTICULARS_OF_SITE - REGISTERED_OWNER zmíněný ve starém template
    NENÍ v seznamu 'fields', tedy není přes API vůbec dostupný, a i tak
    ho do outFields záměrně nedáváme. Používáme returnCentroid, abychom
    z polygonu dostali reprezentativní GPS bod rovnou ve WGS84.
    """
    base_url = "https://services1.arcgis.com/0g8o874l5un2eDgz/arcgis/rest/services/DerelictSitesRegister/FeatureServer/0/query"
    print("📥 Stahuji Roscommon...")
    params = {
        "where": "1=1",
        "outFields": "DS_NUMBER,TOWNLAND,SITUATED_AT,PARTICULARS_OF_SITE",
        "returnCentroid": "true",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(base_url, params=params, timeout=60)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    data = resp.json()
    count = 0
    for feat in data.get("features", []):
        attrs = feat["attributes"]
        centroid = feat.get("centroid") or {}
        address_parts = [attrs.get("SITUATED_AT"), attrs.get("TOWNLAND")]
        address = ", ".join(fix_mojibake(p).strip() for p in address_parts if p and p.strip())
        if not address:
            continue
        writer.writerow({
            "council": "Roscommon",
            "register_ref": attrs.get("DS_NUMBER") or "",
            "address": address,
            "electoral_area": "",
            "notice_date": "",
            "entered_date": "",
            "valuation": "",
            "longitude": centroid.get("x", ""),
            "latitude": centroid.get("y", ""),
            "source_url": "https://data.gov.ie/dataset/derelict-sites-register-roscommon5",
        })
        count += 1
    print(f"  ↳ Roscommon: {count} záznamů")


def fetch_cork(writer):
    """Cork City Council - CKAN datastore (data.gov.ie samotné). Sloupce:
    Reg Entry No., DSP Ref, Other file ref, Address, Date Entry Reg. -
    žádné pole o vlastníkovi.
    """
    print("📥 Stahuji Cork City...")
    resp = requests.get(
        "https://data.gov.ie/api/3/action/datastore_search",
        params={"resource_id": "cab9ab49-6af6-4304-82fb-a7d82ed8c9ac", "limit": 500},
        timeout=60,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    records = resp.json()["result"]["records"]
    count = 0
    for row in records:
        address = (row.get("Address") or "").strip()
        ref = str(row.get("DSP Ref") or "").strip()
        if not address or not ref:
            continue
        entered_date = (row.get("Date Entry Reg.") or "")[:10]  # "YYYY-MM-DDT00:00:00" -> ISO datum
        writer.writerow({
            "council": "Cork City",
            "register_ref": ref,
            "address": address,
            "electoral_area": "",
            "notice_date": "",
            "entered_date": entered_date,
            "valuation": "",
            "longitude": "",
            "latitude": "",
            "source_url": "https://data.gov.ie/dataset/cork-city-council-derelict-site-register",
        })
        count += 1
    print(f"  ↳ Cork City: {count} záznamů")


def fetch_dcc_vacant(writer):
    """Dublin City Council - Vacant Sites Register, přímé CSV. Sloupce
    OBSAHUJÍ 'Ownership' a 'Owner address' - ty se ZÁMĚRNĚ nikdy nečtou.
    """
    url = "https://data.smartdublin.ie/dataset/a3f67387-918f-4195-90d7-1199331fabe4/resource/d3b5ed8b-e99b-46e0-a46e-4295af20ede8/download/vacantsitesregister-12042023.csv"
    print("📥 Stahuji Dublin City (Vacant Sites)...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    lines = resp.content.decode("utf-8-sig").splitlines()
    reader = csv.DictReader(lines)
    count = 0
    for row in reader:
        address = fix_mojibake((row.get("Address of Property") or "").strip())
        ref = (row.get("Register No") or "").strip()
        if not address or not ref:
            continue
        writer.writerow({
            "council": "Dublin City (Vacant)",
            "register_ref": ref,
            "address": address,
            "electoral_area": "",
            "notice_date": "",
            "entered_date": parse_dmy_date(row.get("Date entered on Register")),
            "valuation": (row.get("Market Value") or "").strip(),
            "longitude": "",
            "latitude": "",
            "source_url": "https://data.gov.ie/dataset/vacant-sites-register-dcc",
        })
        count += 1
    print(f"  ↳ Dublin City (Vacant): {count} záznamů")


def main():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        fetch_dlr(writer)
        fetch_sdcc(writer)
        fetch_fingal(writer)
        fetch_roscommon(writer)
        fetch_cork(writer)
        fetch_dcc_vacant(writer)
    print(f"✅ Hotovo! {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
