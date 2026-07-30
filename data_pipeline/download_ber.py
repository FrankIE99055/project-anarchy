"""
download_ber.py
-----------------
Stáhne kompletní BER Research Tool dataset (SEAI) - obsahuje adresy
nemovitostí a jejich energetické štítky (BER rating, datum vydání atd.)
Toto je jediný BER zdroj s bulk přístupem k adresám - individuální
vyhledávač (ndber.seai.ie/pass) vyžaduje už znát konkrétní BER/MPRN
číslo, takže není vhodný/možný pro hromadné stažení.

Stránka je klasický ASP.NET WebForms formulář (postback, ne statický
odkaz) - simulujeme klik na tlačítko "Download All Data" pomocí POST
requestu se zachovanými hidden __VIEWSTATE poli.

Zdroj: https://ndber.seai.ie/BERResearchTool/Register/Register.aspx
T&C: https://ndber.seai.ie/BERResearchTool/TnC.pdf
"""
import os
import re
from urllib.parse import urljoin
import requests

PAGE_URL = "https://ndber.seai.ie/BERResearchTool/Register/Register.aspx"
DOWNLOAD_BUTTON_NAME = "ctl00$DefaultContent$BERSearch$dfExcelDownlaod$DownloadAllData"

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
OUTPUT_ZIP = os.path.join(RAW_DATA_DIR, "BER-ALL.zip")

HIDDEN_FIELD_NAMES = [
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
    "__EVENTTARGET",
    "__EVENTARGUMENT",
]


def extract_hidden_fields(html: str) -> dict:
    fields = {}
    for name in HIDDEN_FIELD_NAMES:
        match = re.search(
            rf'id="{re.escape(name)}"[^>]*value="([^"]*)"', html
        ) or re.search(
            rf'name="{re.escape(name)}"[^>]*value="([^"]*)"', html
        )
        fields[name] = match.group(1) if match else ""
    return fields


def main():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (ProjectAnarchy data pipeline)"})

    print(f"📡 Načítám formulář: {PAGE_URL}")
    resp = session.get(PAGE_URL, timeout=60)
    resp.raise_for_status()
    fields = extract_hidden_fields(resp.text)

    if not fields.get("__VIEWSTATE"):
        raise RuntimeError("Nepodařilo se najít __VIEWSTATE - struktura stránky se možná změnila.")

    # Formulář má <form action="./search.aspx"> - POST se musí poslat na
    # skutečnou action URL, ne zpět na Register.aspx.
    action_match = re.search(r'<form[^>]*action="([^"]*)"', resp.text)
    post_url = urljoin(resp.url, action_match.group(1)) if action_match else PAGE_URL
    print(f"   Formulář se odesílá na: {post_url}")

    form_data = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": fields["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": fields["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION": fields["__EVENTVALIDATION"],
        DOWNLOAD_BUTTON_NAME: "Download All Data",
    }

    print("📥 Odesílám požadavek na stažení celého datasetu (může trvat, soubor je velký)...")
    dl = session.post(post_url, data=form_data, timeout=300)
    dl.raise_for_status()

    content_type = dl.headers.get("Content-Type", "")
    if "zip" not in content_type and not dl.content[:2] == b"PK":
        snippet = dl.text[:500] if "html" in content_type else "(binární obsah)"
        raise RuntimeError(
            f"Odpověď nevypadá jako ZIP (Content-Type: {content_type}). "
            f"Možná se změnila struktura formuláře. Ukázka odpovědi: {snippet}"
        )

    with open(OUTPUT_ZIP, "wb") as f:
        f.write(dl.content)

    print(f"✅ Staženo: {OUTPUT_ZIP} ({len(dl.content) / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
