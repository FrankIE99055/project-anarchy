"""
download_ppr.py
----------------
Stáhne kompletní ZIP archiv Property Price Register (PSRA) obsahující
všechny záznamy o prodejích nemovitostí v Irsku od roku 2010 a rozbalí
CSV soubor do složky raw_data/.

Zdroj: https://www.propertypriceregister.ie/
"""
import os
import zipfile
import requests

PPR_URL = "https://www.propertypriceregister.ie/website/npsra/ppr/npsra-ppr.nsf/Downloads/PPR-ALL.zip/$FILE/PPR-ALL.zip"
RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
ZIP_PATH = os.path.join(RAW_DATA_DIR, "PPR-ALL.zip")


def download_ppr_zip():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)

    print(f"📥 Stahuji Property Price Register z: {PPR_URL}")
    headers = {"User-Agent": "Mozilla/5.0 (ProjectAnarchy data pipeline)"}
    response = requests.get(PPR_URL, headers=headers, timeout=120)
    response.raise_for_status()

    with open(ZIP_PATH, "wb") as f:
        f.write(response.content)
    print(f"✅ Staženo: {ZIP_PATH} ({len(response.content) / 1_000_000:.1f} MB)")

    print("📦 Rozbaluji CSV...")
    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(RAW_DATA_DIR)
        extracted_files = zip_ref.namelist()

    print(f"✅ Rozbaleno: {extracted_files}")
    return [os.path.join(RAW_DATA_DIR, name) for name in extracted_files]


if __name__ == "__main__":
    download_ppr_zip()
