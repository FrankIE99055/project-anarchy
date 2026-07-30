import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Načtení proměnných z .env souboru - bezpečné uložení klíčů
load_dotenv(dotenv_path="../.env")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("❌ Chyba: Supabase URL nebo KEY chybí v .env souboru.")
    exit(1)

try:
    # Vytvoření Supabase klienta
    supabase: Client = create_client(url, key)
    print("✅ Úspěšně incializováno připojení k Supabase!")
    
    # Rychlý test dotazu na systémovou tabulku nebo prázdný požadavek (pokud ještě nemáme tabulky)
    # Zde zatím jen otestujeme sestavení klienta
    print("   Klient je připraven k nahrávání a stahování dat.")
except Exception as e:
    print(f"❌ Nastala chyba při připojování: {e}")
