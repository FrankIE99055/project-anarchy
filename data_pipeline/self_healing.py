"""
self_healing.py
-----------------
Krok 1 ("Inteligentní sběr dat / self-healing scraper") z návrhu
agentické AI pipeline pro Project Anarchy.

BEZPEČNOSTNÍ ROZHODNUTÍ (důležité, čti před použitím): tenhle modul
NIKDY automaticky nespustí kód, který DeepSeek vygeneruje jako opravu.
Automatické spouštění kódu navrženého jazykovým modelem bez lidské
kontroly je vážné bezpečnostní riziko - škodlivě upravená zdrojová
stránka by teoreticky mohla (prompt injection) přimět model navrhnout
kód, který by se sám spustil, a i bez zlého úmyslu by špatně opravený
scraper mohl potichu začít sbírat nesprávná data (přesně to, čemu se
tenhle projekt snaží vyhnout).

Místo autonomní opravy tenhle modul:
1. Nechá scraper selhat normálně (výjimka se VŽDY znovu vyhodí -
   pipeline se nikdy potichu "neopraví" sama).
2. Pošle DeepSeeku traceback + vzorek syrové odpovědi/HTML, které
   scraper naposledy dostal.
3. Uloží navrženou diagnózu + opravený kód do
   `self_heal_suggestions/<script>_<timestamp>.md` pro ČLOVĚKA, který
   návrh zkontroluje a případně ručně nasadí.
"""
import json
import os
import traceback
from datetime import datetime, timezone
from typing import Callable, Optional, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

SUGGESTIONS_DIR = os.path.join(os.path.dirname(__file__), "self_heal_suggestions")

T = TypeVar("T")


class ScraperFixSuggestion(BaseModel):
    diagnosis: str = Field(..., min_length=5, max_length=1000)
    suggested_fix_explanation: str = Field(..., min_length=5, max_length=1500)
    patched_code: str = Field(..., min_length=1, max_length=8000)


_SYSTEM_PROMPT = (
    "You are a senior Python web-scraping engineer maintaining resilient "
    "scrapers (requests/BeautifulSoup/Playwright) against Irish public data "
    "registers whose HTML/API structure occasionally changes without notice. "
    "You are given the scraper script name, the Python traceback of a failure, "
    "and a sample of the raw page/response content the scraper just received. "
    "Diagnose what most likely changed and propose a corrected version of the "
    "relevant function.\n\n"
    "Do not invent selectors, field names, or structure that aren't visible in "
    "the provided sample - if the sample doesn't give you enough to tell what "
    "changed, say so plainly in `diagnosis` and keep `patched_code` as a "
    "minimal, safe placeholder (e.g. a function body of just `pass` with a "
    "comment explaining what a human needs to check) rather than guessing.\n\n"
    "Respond with ONLY a JSON object: {\"diagnosis\": str, "
    "\"suggested_fix_explanation\": str, \"patched_code\": str}"
)


def _call_deepseek_json(system_prompt: str, user_prompt: str, schema, max_retries: int = 1):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error = None
    for _ in range(max_retries + 1):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=1500,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[4:] if raw.lower().startswith("json") else raw
        try:
            parsed = json.loads(raw)
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"Invalid response: {exc}. Return ONLY valid JSON matching the schema.",
                }
            )
    raise ValueError(f"DeepSeek did not return a valid fix suggestion: {last_error}")


def run_with_self_healing(
    script_name: str,
    func: Callable[..., T],
    *args,
    context_sample_fn: Optional[Callable[[], Optional[str]]] = None,
    **kwargs,
) -> T:
    """Spustí `func(*args, **kwargs)`. Pokud selže, zavolá DeepSeek pro
    diagnózu + návrh opravy a ULOŽÍ ho do souboru pro lidskou kontrolu -
    NIKDY ho automaticky nespustí. Původní výjimka se VŽDY znovu vyhodí,
    takže pipeline nikdy tiše nepokračuje se špatnými/chybějícími daty.

    `context_sample_fn` (volitelné) je callback zavolaný AŽ PO selhání,
    který má vrátit vzorek posledního syrového obsahu (HTML/JSON), který
    scraper viděl - typicky čtení modulové proměnné aktualizované uvnitř
    `func` při každém requestu.
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        tb = traceback.format_exc()
        context_sample = None
        if context_sample_fn:
            try:
                context_sample = context_sample_fn()
            except Exception:
                context_sample = None

        if DEEPSEEK_API_KEY:
            try:
                _save_suggestion(script_name, tb, context_sample)
            except Exception as suggestion_error:
                print(f"[self_healing] Could not generate fix suggestion: {suggestion_error}")
        else:
            print("[self_healing] DEEPSEEK_API_KEY not set - skipping fix suggestion.")
        raise exc


def _save_suggestion(script_name: str, traceback_text: str, context_sample: Optional[str]) -> str:
    user_prompt = (
        f"Scraper script: {script_name}\n\n"
        f"Traceback:\n{traceback_text}\n\n"
        f"Sample of raw content last received (truncated to 4000 chars):\n"
        f"{(context_sample or '(none captured)')[:4000]}"
    )
    suggestion = _call_deepseek_json(_SYSTEM_PROMPT, user_prompt, ScraperFixSuggestion)

    os.makedirs(SUGGESTIONS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = script_name.replace("/", "_").replace("\\", "_")
    out_path = os.path.join(SUGGESTIONS_DIR, f"{safe_name}_{timestamp}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Self-heal suggestion for {script_name}\n\n")
        f.write(f"Generated: {timestamp}\n\n")
        f.write("**This patch was NOT applied automatically - review before using.**\n\n")
        f.write("## Diagnosis\n\n" + suggestion.diagnosis + "\n\n")
        f.write("## Suggested fix\n\n" + suggestion.suggested_fix_explanation + "\n\n")
        f.write("## Patched code\n\n")
        f.write("```python\n" + suggestion.patched_code + "\n```\n")

    print(f"[self_healing] Fix suggestion saved to {out_path} - review before applying manually.")
    return out_path
