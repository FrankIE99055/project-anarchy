"""
address_cleaning.py
--------------------
Krok 2 ("Čištění dat a párování na Eircode") z návrhu agentické pipeline
- ale s jednou důležitou opravou kvůli přesnosti dat.

DŮLEŽITÉ: DeepSeek (ani žádný jiný LLM) NEUMÍ a NESMÍ sám "vymyslet"
platný irský Eircode z textu adresy. Eircode je nesekvenční identifikátor
(Routing Key + náhodný Unique Identifier) přidělovaný An Post - není
odvoditelný z adresy žádným algoritmem ani jazykovým modelem. Nechat AI
"doplnit Eircode" by znamenalo čistou halucinaci - přesně to, čemu se
tahle pipeline má vyhnout.

Skutečné párování na Eircode v Project Anarchy proto dělá VÝHRADNĚ
deterministické párování v databázi (townland gazetteer, Eircode přímo
z Daft.ie inzerátu - viz 16_townland_geocoding.sql). Tahle vrstva řeší
jen to, co LLM umí spolehlivě a bezpečně udělat s chaotickým textem
adresy z veřejných registrů (PPR apod.):

1. Normalizace/oprava překlepů a nekonzistentního zápisu (bez přidávání
   informací, které v textu nejsou).
2. Rozpoznání irského hrabství (county), pokud je jednoznačně patrné.
3. Detekce a redakce jména osoby (GDPR), pokud se v surovém textu
   objeví (např. omylem vložené jméno vlastníka).

Výstup je ověřen přes `ai_schemas.call_deepseek_json` proti schématu
`CleanedAddress` - když model formát poruší (nebo by se přesto pokusil
vrátit Eircode navíc mimo schéma), systém ho nepustí dál.
"""
from openai import OpenAI

from ai_schemas import CleanedAddress, call_deepseek_json

_SYSTEM_PROMPT = (
    "You are a data-cleaning assistant for an Irish property register. You receive "
    "one raw, possibly messy address string taken from a public register (typos, "
    "inconsistent casing/abbreviations, occasionally a person's name accidentally "
    "included alongside the address).\n\n"
    "Your job:\n"
    "1) Produce a normalised, human-readable version of the address in "
    "`clean_address` - correct obvious typos/abbreviations and casing, but do NOT "
    "add any information that isn't implied by the input, and do not reorder facts "
    "you are unsure about.\n"
    "2) Identify the Irish county in `county` ONLY if it is clearly stated or "
    "unambiguously implied by a well-known place name; otherwise set it to null - "
    "never guess.\n"
    "3) Set `contains_personal_data` to true if the input contains what looks like "
    "a person's name (owner/occupier/applicant). If true, `redacted_address` must "
    "be the same as `clean_address` but with that name removed/replaced by "
    "'[REDACTED]'. If false, `redacted_address` must equal `clean_address`.\n"
    "4) NEVER output an Eircode, postcode, or any identifier that is not present "
    "verbatim in the input. Eircodes cannot be inferred from an address - do not "
    "invent one under any circumstances, even if you think you know the area well.\n"
    "5) Set `confidence` (\"high\"|\"medium\"|\"low\") to how confident you are that "
    "the cleaned address is accurate.\n\n"
    "Respond with ONLY a JSON object: {\"clean_address\": str, \"county\": str|null, "
    "\"contains_personal_data\": bool, \"redacted_address\": str, "
    "\"confidence\": \"high\"|\"medium\"|\"low\"}"
)


def clean_address(ai_client: OpenAI, raw_address: str) -> CleanedAddress:
    """Vyčistí a GDPR-anonymizuje jednu syrovou adresu. Nikdy nevrací
    Eircode - viz vysvětlení v hlavičce modulu."""
    return call_deepseek_json(
        ai_client,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=f"Raw address: {raw_address}",
        schema=CleanedAddress,
        temperature=0.1,
        max_tokens=400,
    )
