from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import lru_cache
from typing import Any

from dotenv import dotenv_values
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain_openai import ChatOpenAI

from punkathon_agent.models.finance import (
    BatchClassificazioneMovimenti,
    CATEGORIA_TO_MACRO_CATEGORIA,
    CategoriaSpesa,
    ClassificazioneMovimento,
    MacroCategoriaSpesa,
    serialize_classification_schema,
)
from punkathon_agent.punkagent.constants import ENV_PATH

LEGACY_RESTAURANT_BAR_CATEGORY = "Ristoranti | Bar"
LEGACY_MEDICAL_PHARMACY_CATEGORY = "Spese Mediche e Farmacia"

RESTAURANT_KEYWORDS = {
    "fradiavolo",
    "hamburger",
    "osteria",
    "panino",
    "pizzeria",
    "pizza",
    "ristorante",
    "ristoranti",
    "sushi",
    "tavola",
    "trattoria",
}
BAR_KEYWORDS = {
    "aperitivo",
    "bar",
    "bistrot",
    "buffet",
    "caffe",
    "caffetteria",
    "cocktail",
    "espresso",
    "moneynet",
    "pub",
}
PHARMACY_KEYWORDS = {"farmacia", "parafarmacia"}
MEDICAL_KEYWORDS = {
    "clinica",
    "dent",
    "medic",
    "ospedal",
    "psicolog",
    "sedes sapientiae",
    "terapia",
    "unobravo",
    "visita",
}
SATISPAY_KEYWORDS = {"satispay"}
PRELIEVI_KEYWORDS = {"prelievi", "prelievo", "prelievo sportello", "prelievo bancomat"}
BONIFICI_KEYWORDS = {"bonific", "giroconti in uscita", "giroconto", "giroconti"}


def _resolve_openai_api_key() -> str | None:
    file_values = dotenv_values(ENV_PATH)
    file_key = file_values.get("OPENAI_API_KEY")
    env_key = os.getenv("OPENAI_API_KEY")
    return file_key or env_key


def _build_classifier_model(
    model: str = "gpt-5.4",
    reasoning_effort: str = "low",
    verbosity: str = "low",
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=_resolve_openai_api_key(),
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
    )


@lru_cache(maxsize=1)
def _build_classification_agent() -> Any:
    llm = _build_classifier_model()
    return create_agent(
        model=llm,
        response_format=ProviderStrategy(BatchClassificazioneMovimenti),
    )


def _build_classification_prompt(movimenti: list[dict[str, Any]]) -> str:
    categories = "\n".join(
        f"- {categoria.value} -> {CATEGORIA_TO_MACRO_CATEGORIA[categoria].value}"
        for categoria in CategoriaSpesa
        if categoria != CategoriaSpesa.ENTRATE
    )
    payload = json.dumps(movimenti, ensure_ascii=False, indent=2)
    return f"""Classifica ciascun movimento bancario in modo coerente.

Regole obbligatorie:
- Usa solo una delle categorie consentite qui sotto.
- Restituisci esattamente una classificazione per ogni `indice`.
- La `macrocategoria` deve essere coerente con la `categoria`.
- Non inventare nuove categorie o macrocategorie.
- Se il movimento e' ambiguo, usa `Altro Non Essenziale`.
- I movimenti forniti qui sono spese o uscite: non usare `Entrate`.
- Il campo `note` puo' contenere hint forti dalla fonte originale, come categoria banca o stato di contabilizzazione: usalo.
- Se nelle note o nella descrizione compare `satispay`, classifica come `Satispay`.
- Se nelle note o nella descrizione compare `prelievi`, `prelievo sportello` o `prelievo bancomat`, classifica come `Prelievi`.
- Se nelle note o nella descrizione compare `giroconti in uscita`, `giroconto` o un trasferimento/bonifico in uscita che non e' chiaramente affitto, classifica come `Bonifici` e non come `Affitto o Mutuo`.
- Se nelle note compare `generi alimentari e supermercato`, classifica come `Alimentazione` salvo contraddizioni evidenti nella descrizione.
- `Ristoranti` e `Bar` sono categorie distinte: non unirle mai. Se il merchant sembra un bar, buffet, caffe', pub o aperitivo usa `Bar`; se sembra pizzeria, ristorante, paninoteca o simili usa `Ristoranti`.
- `Spese Mediche` e `Farmacia` sono categorie distinte: non unirle mai. Se il merchant e' una farmacia o parafarmacia usa `Farmacia`; per visite, terapie, psicologo, cliniche e spese sanitarie usa `Spese Mediche`.
- Se nelle note compare `tv, internet, telefono`, classifica come `Telefono / Internet`.

Categorie consentite:
{categories}

Movimenti da classificare:
{payload}
"""


def _normalize_hint(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip()


def _contains_any_hint(value: str, keywords: set[str]) -> bool:
    return any(keyword in value for keyword in keywords)


def _classification_from_category(category: CategoriaSpesa) -> ClassificazioneMovimento:
    return ClassificazioneMovimento(
        categoria=category,
        macrocategoria=CATEGORIA_TO_MACRO_CATEGORIA[category],
    )


def _classify_restaurant_or_bar(description: str, note: str) -> CategoriaSpesa | None:
    description_has_restaurant_hint = _contains_any_hint(description, RESTAURANT_KEYWORDS)
    description_has_bar_hint = _contains_any_hint(description, BAR_KEYWORDS)

    if description_has_restaurant_hint and not description_has_bar_hint:
        return CategoriaSpesa.RISTORANTI
    if description_has_bar_hint and not description_has_restaurant_hint:
        return CategoriaSpesa.BAR

    note_has_restaurant_hint = "ristoranti" in note or "ristorante" in note
    note_has_bar_hint = " bar" in f" {note}" or note.endswith("bar")

    if note_has_restaurant_hint and not note_has_bar_hint:
        return CategoriaSpesa.RISTORANTI
    if note_has_bar_hint and not note_has_restaurant_hint:
        return CategoriaSpesa.BAR

    if "ristoranti e bar" in note and not description_has_bar_hint:
        return CategoriaSpesa.RISTORANTI

    return None


def _classify_medical_or_pharmacy(description: str, note: str) -> CategoriaSpesa | None:
    if _contains_any_hint(description, PHARMACY_KEYWORDS) or _contains_any_hint(note, PHARMACY_KEYWORDS):
        return CategoriaSpesa.FARMACIA

    if "spese mediche" in note or _contains_any_hint(description, MEDICAL_KEYWORDS) or _contains_any_hint(note, MEDICAL_KEYWORDS):
        return CategoriaSpesa.SPESE_MEDICHE

    return None


def split_legacy_category_label(category: str | None, descrizione: str | None = None, note: str | None = None) -> str | None:
    if category is None:
        return None

    description = _normalize_hint(descrizione)
    normalized_note = _normalize_hint(note)

    if category == LEGACY_RESTAURANT_BAR_CATEGORY:
        split_category = _classify_restaurant_or_bar(description, normalized_note) or CategoriaSpesa.RISTORANTI
        return split_category.value

    if category == LEGACY_MEDICAL_PHARMACY_CATEGORY:
        split_category = _classify_medical_or_pharmacy(description, normalized_note) or CategoriaSpesa.SPESE_MEDICHE
        return split_category.value

    return category


def _rule_based_classification(movimento: dict[str, Any]) -> ClassificazioneMovimento | None:
    description = _normalize_hint(str(movimento.get("descrizione") or ""))
    note = _normalize_hint(str(movimento.get("note") or ""))
    combined = f"{description} {note}".strip()

    if not combined:
        return None

    if _contains_any_hint(combined, SATISPAY_KEYWORDS):
        return _classification_from_category(CategoriaSpesa.SATISPAY)

    if _contains_any_hint(combined, PRELIEVI_KEYWORDS):
        return _classification_from_category(CategoriaSpesa.PRELIEVI)

    if _contains_any_hint(combined, BONIFICI_KEYWORDS):
        return _classification_from_category(CategoriaSpesa.BONIFICI)

    if "generi alimentari e supermercato" in combined:
        return _classification_from_category(CategoriaSpesa.ALIMENTAZIONE)

    if "ristoranti e bar" in combined or "ristoranti" in note or "ristorante" in note or " bar" in f" {note}":
        food_category = _classify_restaurant_or_bar(description, note)
        if food_category is not None:
            return _classification_from_category(food_category)

    if "spese mediche" in combined or "farmacia" in combined:
        health_category = _classify_medical_or_pharmacy(description, note)
        if health_category is not None:
            return _classification_from_category(health_category)

    if "trasporti, noleggi, taxi e parcheggi" in combined:
        return _classification_from_category(CategoriaSpesa.TRASPORTO)

    if "tv, internet, telefono" in combined:
        return _classification_from_category(CategoriaSpesa.TELEFONO_INTERNET)

    if "animali domestici" in combined:
        return _classification_from_category(CategoriaSpesa.PET)

    if "assicurazioni" in combined and "polizze" in combined:
        return _classification_from_category(CategoriaSpesa.ASSICURAZIONI)

    return None


def classifica_movimenti(movimenti: list[dict[str, Any]]) -> list[ClassificazioneMovimento]:
    if not movimenti:
        return []

    classificazioni: list[ClassificazioneMovimento | None] = [None] * len(movimenti)
    movimenti_da_classificare: list[dict[str, Any]] = []

    for indice, movimento in enumerate(movimenti):
        importo = float(movimento["importo"])
        if importo > 0:
            classificazioni[indice] = ClassificazioneMovimento(
                categoria=CategoriaSpesa.ENTRATE,
                macrocategoria=MacroCategoriaSpesa.ENTRATE,
            )
            continue

        rule_based = _rule_based_classification(movimento)
        if rule_based is not None:
            classificazioni[indice] = rule_based
            continue

        movimenti_da_classificare.append(
            {
                "indice": indice,
                "descrizione": movimento["descrizione"],
                "note": movimento.get("note"),
                "importo": importo,
            }
        )

    if movimenti_da_classificare:
        result = _build_classification_agent().invoke(
            {"messages": [{"role": "user", "content": _build_classification_prompt(movimenti_da_classificare)}]}
        )
        structured_response = result.get("structured_response")
        if not isinstance(structured_response, BatchClassificazioneMovimenti):
            raise ValueError("La classificazione AI non ha restituito un output strutturato valido.")

        requested_indices = {item["indice"] for item in movimenti_da_classificare}
        seen_indices: set[int] = set()

        for item in structured_response.classificazioni:
            if item.indice not in requested_indices:
                raise ValueError(f"Indice di classificazione inatteso: {item.indice}.")
            if item.indice in seen_indices:
                raise ValueError(f"Indice duplicato nella classificazione AI: {item.indice}.")
            if item.categoria == CategoriaSpesa.ENTRATE or item.macrocategoria == MacroCategoriaSpesa.ENTRATE:
                raise ValueError(f"La classificazione AI ha marcato come entrata una spesa all'indice {item.indice}.")

            seen_indices.add(item.indice)
            classificazioni[item.indice] = ClassificazioneMovimento(
                categoria=item.categoria,
                macrocategoria=item.macrocategoria,
            )

        missing_indices = requested_indices - seen_indices
        if missing_indices:
            missing_text = ", ".join(str(item) for item in sorted(missing_indices))
            raise ValueError(f"Classificazione AI incompleta. Mancano gli indici: {missing_text}.")

    missing = [str(index) for index, item in enumerate(classificazioni) if item is None]
    if missing:
        raise ValueError(f"Classificazione AI incompleta. Mancano gli indici: {', '.join(missing)}.")

    return [item for item in classificazioni if item is not None]


__all__ = [
    "CATEGORIA_TO_MACRO_CATEGORIA",
    "CategoriaSpesa",
    "MacroCategoriaSpesa",
    "classifica_movimenti",
    "serialize_classification_schema",
    "split_legacy_category_label",
]
