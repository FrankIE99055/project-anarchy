"""
ai_schemas.py
-------------
Sdílená vrstva pro "Pravidlo #2" z agentické AI pipeline: DeepSeek nikdy
nesmí projít do zbytku systému s výstupem, který nesedí na přesné
schéma. Každé volání DeepSeeku, které má vrátit strukturovaná data
(ne volný text jako /explain), jde přes `call_deepseek_json()` a je
validované Pydantic modelem odsud.

Chování při špatném výstupu: DeepSeek dostane JSON mode
(`response_format={"type": "json_object"}`), po chybě parsování/validace
se mu chyba pošle zpět a dostane jeden pokus na opravu (celkem
`max_retries + 1` pokusů). Pokud ani pak nevrátí platný JSON dle
schématu, `call_deepseek_json` vyhodí `ValueError` - volající vrstva
(main.py) to musí zachytit a vrátit uživateli chybu (503/502), NIKDY
nepouštět neověřená data dál (např. do `properties.propensity_score`).
"""
import json
from typing import Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

T = TypeVar("T", bound=BaseModel)


def call_deepseek_json(
    ai_client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    model: str = "deepseek-chat",
    temperature: float = 0.1,
    max_retries: int = 2,
    max_tokens: int = 800,
) -> T:
    """Volá DeepSeek v JSON mode a ověří odpověď proti `schema`. Při
    neplatném JSONu/schématu pošle modelu chybu zpět a zkusí to znovu
    (max `max_retries`x), než se vzdá."""
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error: Optional[Exception] = None

    for _ in range(max_retries + 1):
        response = ai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        raw = (response.choices[0].message.content or "").strip()
        # DeepSeek can wrap JSON in ```json fences despite JSON mode - strip defensively.
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
                    "content": (
                        f"That response was invalid: {exc}\n"
                        "Respond again with ONLY a single valid JSON object matching "
                        "the required schema - no markdown fences, no other text."
                    ),
                }
            )

    raise ValueError(
        f"DeepSeek did not return a schema-valid response after {max_retries + 1} attempts: {last_error}"
    )


class CleanedAddress(BaseModel):
    """Výstup kroku 2 (čištění + GDPR anonymizace adresy). Záměrně
    NEOBSAHUJE eircode - viz vysvětlení v address_cleaning.py, proč AI
    nikdy nesmí Eircode sama vymýšlet."""

    clean_address: str = Field(..., min_length=3, max_length=300)
    county: Optional[str] = Field(None, max_length=50)
    contains_personal_data: bool
    redacted_address: str = Field(..., min_length=3, max_length=300)
    confidence: str = Field(..., pattern="^(high|medium|low)$")


class TimelineAssessment(BaseModel):
    """Výstup kroku 3 (CoT analýza timeline jedné nemovitosti). Model
    dostává POUZE fakta z naší DB (RAG, pravidlo #1) a smí jen navrhnout
    úpravu skóre + shrnutí - nikdy si signály nevymýšlí."""

    reasoning_summary: str = Field(..., min_length=10, max_length=600)
    trigger_signals: list[str] = Field(..., max_length=8)
    score_adjustment: int = Field(..., ge=-10, le=25)
    confidence: str = Field(..., pattern="^(high|medium|low)$")


class InvestorReportSections(BaseModel):
    """Výstup kroku 4 (report pro investora) - tři Markdown sekce."""

    property_overview: str = Field(..., min_length=10, max_length=1500)
    trigger_signals_analysis: str = Field(..., min_length=10, max_length=2000)
    risk_assessment: str = Field(..., min_length=10, max_length=1500)


class MarketReportSections(BaseModel):
    """Výstup čtvrtletního AI market reportu (celý irský trh, ne jedna
    nemovitost) - tři Markdown sekce nad reálnými agregáty z DB."""

    market_overview: str = Field(..., min_length=10, max_length=1500)
    trend_analysis: str = Field(..., min_length=10, max_length=2000)
    risk_assessment: str = Field(..., min_length=10, max_length=1500)
