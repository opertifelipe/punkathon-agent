from __future__ import annotations

import json
import re
import unicodedata
from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from sqlmodel import select

from punkathon_agent.db import create_database, get_session
from punkathon_agent.models.agent import MessageContent
from punkathon_agent.models.db import MovimentoBancario, PunkUser, Utente
from punkathon_agent.models.finance import CategoriaSpesa, MacroCategoriaSpesa
from punkathon_agent.punkagent.request_context import get_default_frontend_week_window
from punkathon_agent.punkagent.request_context import get_current_user_id
from punkathon_agent.punkagent.constants import (
    DESCRIPTION_STOPWORDS,
    ESSENTIAL_FIXED_KEYWORDS,
    MAX_QUERY_ROWS,
    RECEIPT_SOURCE_HINTS,
    RECURRING_FIXED_HINTS,
    STATEMENT_SOURCE_HINTS,
)

ESSENTIAL_FIXED_CATEGORIES = {
    CategoriaSpesa.AFFITTO_O_MUTUO.value,
    CategoriaSpesa.CONDOMINIO.value,
    CategoriaSpesa.ACQUA.value,
    CategoriaSpesa.GAS.value,
    CategoriaSpesa.LUCE.value,
    CategoriaSpesa.TELEFONO_INTERNET.value,
    CategoriaSpesa.ASSICURAZIONI.value,
    CategoriaSpesa.MACCHINA.value,
}
NON_ESSENTIAL_FIXED_CATEGORIES = {
    CategoriaSpesa.ABBONAMENTI.value,
    CategoriaSpesa.PALESTRA.value,
}


def _resolve_user_id(user_id: int | None = None) -> int:
    scoped_user_id = user_id if user_id is not None else get_current_user_id()
    if scoped_user_id is None:
        raise RuntimeError("Contesto utente mancante.")
    return scoped_user_id


def _scope_movement_statement(statement: Any, *, user_id: int | None = None) -> Any:
    return statement.where(MovimentoBancario.user_id == _resolve_user_id(user_id))


def _scope_profile_statement(statement: Any, *, user_id: int | None = None) -> Any:
    return statement.where(Utente.user_id == _resolve_user_id(user_id))


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip()


def _canonical_description(value: str) -> str:
    return _normalize_text(value)


def _description_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _canonical_description(value))
        if len(token) >= 4 and token not in DESCRIPTION_STOPWORDS
    }


def _movement_text(movimento: MovimentoBancario) -> str:
    return _normalize_text(" ".join(part for part in (movimento.descrizione, movimento.note or "") if part))


def _movement_source_type(note: str | None) -> str:
    normalized_note = _normalize_text(note)
    if any(hint in normalized_note for hint in STATEMENT_SOURCE_HINTS):
        return "estratto_conto"
    if any(hint in normalized_note for hint in RECEIPT_SOURCE_HINTS):
        return "scontrino"
    return "manuale"


def _source_priority(note: str | None) -> int:
    source_type = _movement_source_type(note)
    if source_type == "estratto_conto":
        return 3
    if source_type == "scontrino":
        return 2
    return 1


def _merge_notes(*notes: str | None) -> str | None:
    merged_parts: list[str] = []
    seen: set[str] = set()

    for note in notes:
        if note is None:
            continue
        normalized_note = note.strip()
        if not normalized_note:
            continue
        fingerprint = _normalize_text(normalized_note)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        merged_parts.append(normalized_note)

    if not merged_parts:
        return None
    return " | ".join(merged_parts)


def _movements_look_like_same_purchase(first: MovimentoBancario, second: MovimentoBancario) -> bool:
    if first.data != second.data:
        return False
    if _round_money(first.importo) != _round_money(second.importo):
        return False

    first_description = _canonical_description(first.descrizione)
    second_description = _canonical_description(second.descrizione)
    if first_description == second_description:
        return True
    if first_description in second_description or second_description in first_description:
        return True

    return bool(_description_tokens(first.descrizione) & _description_tokens(second.descrizione))


def _duplicate_survivor_score(movimento: MovimentoBancario) -> tuple[int, int, int]:
    return (
        _source_priority(movimento.note),
        len((movimento.note or "").strip()),
        len(movimento.descrizione.strip()),
    )


def _has_essential_keyword(normalized_text: str) -> bool:
    return any(keyword in normalized_text for keyword in ESSENTIAL_FIXED_KEYWORDS)


def _has_recurring_fixed_hint(normalized_text: str) -> bool:
    return any(keyword in normalized_text for keyword in RECURRING_FIXED_HINTS)


def _month_bucket(value: date) -> str:
    return value.strftime("%Y-%m")


def _previous_complete_month_window(*, reference_date: date | None = None) -> dict[str, date | str]:
    today = reference_date or date.today()
    current_month_start = today.replace(day=1)
    previous_month_end = current_month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    return {
        "label": _month_bucket(previous_month_start),
        "start_date": previous_month_start,
        "end_date": previous_month_end,
    }


def _week_bucket(value: date) -> str:
    iso_year, iso_week, _ = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _is_essential_fixed_category(category: str | None) -> bool:
    return bool(category and category in ESSENTIAL_FIXED_CATEGORIES)


def _essential_fixed_reason(movimento: MovimentoBancario) -> str | None:
    if _is_essential_fixed_category(movimento.categoria):
        return "categoria fissa essenziale"

    normalized_text = _movement_text(movimento)
    if _has_essential_keyword(normalized_text):
        return "keyword essenziale"

    if movimento.macrocategoria == MacroCategoriaSpesa.SPESE_FISSE.value and _has_recurring_fixed_hint(normalized_text):
        return "ricorrenza fissa"

    return None


def _is_likely_essential_fixed(
    movimento: MovimentoBancario,
    inferred_descriptions: set[str] | None = None,
) -> bool:
    if _is_essential_fixed_category(movimento.categoria):
        return movimento.importo < 0
    if movimento.categoria in NON_ESSENTIAL_FIXED_CATEGORIES:
        return False
    if movimento.macrocategoria == MacroCategoriaSpesa.SPESE_FISSE.value and _essential_fixed_reason(movimento) is not None:
        return movimento.importo < 0
    if movimento.macrocategoria in {
        MacroCategoriaSpesa.SPESE_VARIABILI.value,
        MacroCategoriaSpesa.ENTRATE.value,
    }:
        return False

    canonical_description = _canonical_description(movimento.descrizione)
    if inferred_descriptions and canonical_description in inferred_descriptions:
        return True
    return movimento.importo < 0 and _has_essential_keyword(_movement_text(movimento))


def _calculate_available_budget(
    stipendio_mensile: float | None,
    spese_fisse_essenziali_mensili: float | None,
) -> tuple[float | None, float | None]:
    if stipendio_mensile is None or spese_fisse_essenziali_mensili is None:
        return None, None

    disponibile_mensile = _round_money(stipendio_mensile - spese_fisse_essenziali_mensili)
    if disponibile_mensile is None:
        return None, None
    disponibile_settimanale = _round_money(disponibile_mensile / 5)
    return disponibile_mensile, disponibile_settimanale


def _sync_budget_fields(profile: Utente) -> None:
    disponibile_mensile, disponibile_settimanale = _calculate_available_budget(
        profile.stipendio_mensile,
        profile.spese_fisse_essenziali_mensili,
    )
    profile.disponibile_mensile = disponibile_mensile
    profile.disponibile_settimanale = disponibile_settimanale


def _serialize_movimento(movimento: MovimentoBancario) -> dict[str, Any]:
    return {
        "data": movimento.data.isoformat(),
        "descrizione": movimento.descrizione,
        "importo": _round_money(movimento.importo),
        "note": movimento.note,
        "categoria": movimento.categoria,
        "macrocategoria": movimento.macrocategoria,
    }


def _serialize_expense_preview(movimento: MovimentoBancario) -> dict[str, Any]:
    return {
        "data": movimento.data.isoformat(),
        "descrizione": movimento.descrizione,
        "spesa": _round_money(abs(movimento.importo)),
        "note": movimento.note,
        "categoria": movimento.categoria,
        "macrocategoria": movimento.macrocategoria,
    }


def _serialize_profile(profile: Utente) -> dict[str, Any]:
    return {
        "stipendio_mensile": _round_money(profile.stipendio_mensile),
        "spese_fisse_essenziali_mensili": _round_money(profile.spese_fisse_essenziali_mensili),
        "disponibile_mensile": _round_money(profile.disponibile_mensile),
        "disponibile_settimanale": _round_money(profile.disponibile_settimanale),
        "obiettivo": profile.obiettivo,
        "spese_irrinunciabili": profile.spese_irrinunciabili,
    }


def _compact_fixed_expense_summary(fixed_expense_summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if fixed_expense_summary is None:
        return None

    complete_months = fixed_expense_summary.get("mesi_completi_disponibili") or []
    return {
        "mese_riferimento": fixed_expense_summary.get("mese_riferimento"),
        "spese_fisse_mensili_stimate": fixed_expense_summary.get("spese_fisse_mensili_stimate"),
        "spese_fisse_mese_corrente": fixed_expense_summary.get("spese_fisse_mese_corrente"),
        "mesi_completi_disponibili_count": len(complete_months),
        "metodo": "macrocategoria = Spese Fisse del mese completo precedente",
    }


def build_fixed_expense_context(
    *,
    profile: Utente,
    fixed_expenses_status: str,
    fixed_expenses_evidence: list[dict[str, Any]] | None = None,
    preview_limit: int = 5,
) -> dict[str, Any]:
    safe_preview_limit = max(1, int(preview_limit))
    profile_payload: dict[str, Any] = {
        "campo": "spese_fisse_essenziali_mensili",
        "valore_mensile": _round_money(profile.spese_fisse_essenziali_mensili),
        "stato": fixed_expenses_status,
        "metodo_calcolo": "totale `macrocategoria = Spese Fisse` del mese completo precedente",
        "usa_per": ["budget", "obiettivo", "margine disponibile"],
    }

    if fixed_expenses_evidence:
        profile_payload["evidenze"] = fixed_expenses_evidence[:safe_preview_limit]

    return {
        "richiesta_generica_utente": {
            "usa": "spese_fisse_da_macrocategoria",
            "metodo": "macrocategoria = Spese Fisse del mese completo precedente",
        },
        "profilo_utente": profile_payload,
        "confronto_automatico_consigliato": False,
        "nota": (
            "Il profilo usa lo stesso totale delle spese fisse da macrocategoria, "
            "sincronizzato sul mese completo precedente per budget e margine disponibile."
        ),
    }


def build_fixed_expense_scope_payload(
    *,
    profile: Utente,
    fixed_expenses_status: str,
    fixed_expenses_evidence: list[dict[str, Any]] | None = None,
    preview_limit: int = 5,
    fixed_expense_summary: dict[str, Any] | None = None,
    include_full_macro_summary: bool = False,
) -> dict[str, Any]:
    payload = {
        "contesto_spese_fisse": build_fixed_expense_context(
            profile=profile,
            fixed_expenses_status=fixed_expenses_status,
            fixed_expenses_evidence=fixed_expenses_evidence,
            preview_limit=preview_limit,
        )
    }

    if fixed_expense_summary is not None:
        payload["spese_fisse_da_macrocategoria"] = (
            fixed_expense_summary if include_full_macro_summary else _compact_fixed_expense_summary(fixed_expense_summary)
        )

    return payload


def _profile_missing_fields(profile: Utente) -> list[str]:
    missing_fields: list[str] = []
    if profile.stipendio_mensile is None:
        missing_fields.append("stipendio_mensile")
    if not profile.obiettivo:
        missing_fields.append("obiettivo")
    return missing_fields


def _rows_to_json(rows: list[dict[str, Any]], *, truncated: bool = False) -> str:
    payload: dict[str, Any] = {
        "rows": rows,
        "count": len(rows),
    }
    if truncated:
        payload["truncated"] = True
        payload["message"] = f"Risultato troncato a {MAX_QUERY_ROWS} righe."
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _serialize_duplicate_pair(kept: MovimentoBancario, removed: MovimentoBancario) -> dict[str, Any]:
    return {
        "data": kept.data.isoformat(),
        "importo": _round_money(kept.importo),
        "mantenuto": _serialize_movimento(kept),
        "rimosso": _serialize_movimento(removed),
        "fonti_coinvolte": sorted({_movement_source_type(kept.note), _movement_source_type(removed.note)}),
    }


def _serialize_duplicate_candidate_group(movimenti: list[MovimentoBancario]) -> dict[str, Any]:
    first = movimenti[0]
    return {
        "data": first.data.isoformat(),
        "importo": _round_money(first.importo),
        "fonti_coinvolte": sorted({_movement_source_type(movimento.note) for movimento in movimenti}),
        "rows": [_serialize_movimento(movimento) for movimento in movimenti],
    }


def _deduplicate_movimenti(session: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    statement = _scope_movement_statement(
        select(MovimentoBancario).order_by(MovimentoBancario.data.desc(), MovimentoBancario.descrizione.asc())
    )
    movements = list(session.exec(statement))
    groups: dict[tuple[date, float], list[MovimentoBancario]] = {}

    for movimento in movements:
        groups.setdefault((movimento.data, _round_money(movimento.importo) or 0.0), []).append(movimento)

    removed_duplicates: list[dict[str, Any]] = []

    for group in groups.values():
        if len(group) < 2:
            continue

        survivors: list[MovimentoBancario] = []
        for movimento in sorted(group, key=_duplicate_survivor_score, reverse=True):
            match = next((survivor for survivor in survivors if _movements_look_like_same_purchase(survivor, movimento)), None)
            if match is None:
                survivors.append(movimento)
                continue

            match.note = _merge_notes(match.note, movimento.note)
            removed_duplicates.append(_serialize_duplicate_pair(match, movimento))
            session.delete(movimento)

    session.commit()

    refreshed_movements = list(session.exec(statement))
    refreshed_groups: dict[tuple[date, float], list[MovimentoBancario]] = {}
    for movimento in refreshed_movements:
        refreshed_groups.setdefault((movimento.data, _round_money(movimento.importo) or 0.0), []).append(movimento)

    cross_source_candidates: list[dict[str, Any]] = []
    for group in refreshed_groups.values():
        if len(group) < 2:
            continue
        source_types = {_movement_source_type(movimento.note) for movimento in group}
        if len(source_types) < 2:
            continue
        cross_source_candidates.append(_serialize_duplicate_candidate_group(group))

    return removed_duplicates, cross_source_candidates


def _get_or_create_user_profile(session: Any, *, user_id: int | None = None) -> Utente:
    scoped_user_id = _resolve_user_id(user_id)
    profile = session.exec(_scope_profile_statement(select(Utente), user_id=scoped_user_id)).first()
    if profile is None:
        profile = Utente(user_id=scoped_user_id)
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def _infer_essential_fixed_expense_items_from_movements(
    movements: list[MovimentoBancario],
    *,
    reference_date: date | None = None,
) -> list[dict[str, Any]]:
    today = reference_date or date.today()
    current_month_start = today.replace(day=1)
    complete_months = sorted({_month_bucket(movimento.data) for movimento in movements if movimento.data < current_month_start})

    if not complete_months:
        return []

    matches_by_description: dict[str, dict[str, Any]] = {}
    available_month_count = len(complete_months)

    for movimento in movements:
        if movimento.data >= current_month_start or movimento.importo >= 0:
            continue

        reason = _essential_fixed_reason(movimento)
        if reason is None:
            continue

        canonical_description = _canonical_description(movimento.descrizione)
        month_key = _month_bucket(movimento.data)
        amount = abs(float(movimento.importo))

        current = matches_by_description.get(canonical_description)
        if current is None:
            matches_by_description[canonical_description] = {
                "row": movimento,
                "motivi": {reason},
                "totale_periodo": amount,
                "mesi_presenti": {month_key},
                "totali_per_mese": {month_key: amount},
            }
            continue

        current["motivi"].add(reason)
        current["totale_periodo"] += amount
        current["mesi_presenti"].add(month_key)
        current["totali_per_mese"][month_key] = current["totali_per_mese"].get(month_key, 0.0) + amount
        if movimento.data > current["row"].data:
            current["row"] = movimento

    inferred_items: list[dict[str, Any]] = []
    for canonical_description, match in matches_by_description.items():
        movimento = match["row"]
        total_period = float(match["totale_periodo"])
        average_per_available_month = total_period / available_month_count
        months_present = sorted(match["mesi_presenti"])
        average_when_present = total_period / len(months_present)

        inferred_items.append(
            {
                "chiave": canonical_description,
                "data_riferimento": movimento.data.isoformat(),
                "descrizione": movimento.descrizione,
                "importo_mensile": _round_money(average_per_available_month),
                "media_mensile_sui_mesi_disponibili": _round_money(average_per_available_month),
                "media_mensile_quando_presente": _round_money(average_when_present),
                "totale_periodo": _round_money(total_period),
                "mesi_disponibili": complete_months,
                "mesi_disponibili_count": available_month_count,
                "mesi_presenti": months_present,
                "totali_per_mese": [
                    {
                        "mese": month_key,
                        "importo": _round_money(float(match["totali_per_mese"][month_key])),
                    }
                    for month_key in complete_months
                    if month_key in match["totali_per_mese"]
                ],
                "motivo": ", ".join(sorted(match["motivi"])),
            }
        )

    inferred_items.sort(key=lambda item: item["descrizione"].casefold())
    return inferred_items


def _infer_essential_fixed_expense_items(
    session: Any,
    *,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    movements = _fetch_all_movements(session, user_id=user_id)
    return _infer_essential_fixed_expense_items_from_movements(movements)


def _estimate_essential_fixed_total(items: list[dict[str, Any]]) -> float | None:
    if not items:
        return None
    return _round_money(sum(float(item["importo_mensile"]) for item in items))


def _ensure_estimated_fixed_expenses(
    session: Any,
    profile: Utente,
    *,
    overwrite_existing: bool = False,
    user_id: int | None = None,
    reference_date: date | None = None,
) -> tuple[list[dict[str, Any]], str, bool]:
    all_movements = _fetch_all_movements(session, user_id=user_id)
    fixed_summary = build_fixed_expense_monthly_summary(
        all_movements,
        reference_date=reference_date,
        preview_limit=20,
    )
    evidence = list(fixed_summary.get("dettaglio_voci") or [])
    estimated_total = fixed_summary.get("spese_fisse_mensili_stimate")
    previous_value = _round_money(profile.spese_fisse_essenziali_mensili)

    if estimated_total is None:
        if previous_value is None or not overwrite_existing:
            return evidence, "non_stimabili_dai_movimenti", False

        profile.spese_fisse_essenziali_mensili = None
        _sync_budget_fields(profile)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return evidence, "non_stimabili_dai_movimenti", True

    if previous_value is not None and not overwrite_existing:
        return evidence, "presenti", False

    if previous_value == estimated_total:
        return evidence, "presenti", False

    profile.spese_fisse_essenziali_mensili = estimated_total
    _sync_budget_fields(profile)
    session.add(profile)
    session.commit()
    session.refresh(profile)

    status = "stimate_automaticamente" if previous_value is None else "ricalcolate_automaticamente"
    return evidence, status, True


def _current_user_profile_snapshot() -> dict[str, Any]:
    create_database()
    current_user_id = get_current_user_id()

    with get_session() as session:
        authenticated_user = None
        if current_user_id is not None:
            current_user = session.get(PunkUser, current_user_id)
            if current_user is not None and current_user.id is not None:
                authenticated_user = {
                    "id": current_user.id,
                    "email": current_user.email,
                    "nome": current_user.nome,
                    "cognome": current_user.cognome,
                    "nome_completo": f"{current_user.nome} {current_user.cognome}".strip(),
                    "eta": current_user.eta,
                }

        profile = _get_or_create_user_profile(session)
        fixed_expenses_evidence, fixed_expenses_status, _ = _ensure_estimated_fixed_expenses(
            session,
            profile,
            overwrite_existing=True,
            user_id=current_user_id,
        )
        _sync_budget_fields(profile)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        all_movements = _fetch_all_movements(session)
        movement_count = len(all_movements)
        fixed_summary = build_fixed_expense_monthly_summary(all_movements, preview_limit=3)
        return {
            "utente_autenticato": authenticated_user,
            "conteggio_movimenti_database": movement_count,
            "database_movimenti_vuoto": movement_count == 0,
            "profilo": _serialize_profile(profile),
            "campi_mancanti": _profile_missing_fields(profile),
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=fixed_expenses_evidence,
                preview_limit=3,
                fixed_expense_summary=fixed_summary,
                include_full_macro_summary=False,
            ),
        }


def _inject_profile_context(user_content: MessageContent) -> MessageContent:
    profile_snapshot = _current_user_profile_snapshot()
    profile_context = json.dumps(profile_snapshot, ensure_ascii=False, indent=2)
    authenticated_user = profile_snapshot.get("utente_autenticato")
    profile_header = "Contesto profilo utente corrente dal database:\n"
    empty_dataset_note = ""

    if profile_snapshot.get("database_movimenti_vuoto") is True:
        empty_dataset_note = (
            "Il database dei movimenti bancari e' ancora vuoto. "
            "Invita l'utente ad aggiungere i primi movimenti allegando il PDF dell'estratto conto, "
            "foto di scontrini o ricevute, oppure scrivendoli direttamente in chat.\n"
        )

    if isinstance(authenticated_user, dict) and authenticated_user.get("nome"):
        full_name = str(authenticated_user.get("nome_completo") or authenticated_user["nome"]).strip()
        age = authenticated_user.get("eta")
        age_suffix = f", {age} anni" if age is not None else ""
        profile_header = (
            f"Utente autenticato corrente dal database: {full_name}{age_suffix}. "
            "Quando serve personalizzare la risposta, usa questo nome per rivolgerti all'utente.\n"
            f"{empty_dataset_note}"
            "Contesto profilo utente corrente dal database:\n"
        )
    elif empty_dataset_note:
        profile_header = f"{empty_dataset_note}{profile_header}"

    if isinstance(user_content, str):
        return f"{profile_header}{profile_context}\n\nRichiesta utente:\n{user_content}"

    if not user_content:
        return [
            {
                "type": "text",
                "text": f"{profile_header}{profile_context}",
            }
        ]

    updated_blocks = [dict(block) for block in user_content]
    first_block = updated_blocks[0]
    if first_block.get("type") == "text" and isinstance(first_block.get("text"), str):
        first_block["text"] = f"{profile_header}{profile_context}\n\n{first_block['text']}"
        updated_blocks[0] = first_block
        return updated_blocks

    return [
        {
            "type": "text",
            "text": f"{profile_header}{profile_context}",
        },
        *updated_blocks,
    ]


def _expense_total(movements: list[MovimentoBancario]) -> float:
    return _round_money(sum(abs(movement.importo) for movement in movements if movement.importo < 0)) or 0.0


def _income_total(movements: list[MovimentoBancario]) -> float:
    return _round_money(sum(movement.importo for movement in movements if movement.importo > 0)) or 0.0


def _net_total(movements: list[MovimentoBancario]) -> float:
    return _round_money(sum(movement.importo for movement in movements)) or 0.0


def _top_expense_previews(movements: list[MovimentoBancario], *, limit: int) -> list[dict[str, Any]]:
    expenses = [movement for movement in movements if movement.importo < 0]
    expenses.sort(key=lambda movement: (abs(movement.importo), movement.data), reverse=True)
    return [_serialize_expense_preview(movement) for movement in expenses[:limit]]


def _breakdown_by_field(
    movements: list[MovimentoBancario],
    *,
    field_name: str,
    default_label: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for movement in movements:
        if movement.importo >= 0:
            continue
        label = getattr(movement, field_name) or default_label
        current = grouped.get(label)
        amount = abs(float(movement.importo))

        if current is None:
            grouped[label] = {
                "label": label,
                "spesa_totale": amount,
                "numero_movimenti": 1,
                "ultima_data": movement.data.isoformat(),
            }
            continue

        current["spesa_totale"] += amount
        current["numero_movimenti"] += 1
        if movement.data.isoformat() > current["ultima_data"]:
            current["ultima_data"] = movement.data.isoformat()

    rows = [
        {
            "label": row["label"],
            "spesa_totale": _round_money(float(row["spesa_totale"])) or 0.0,
            "numero_movimenti": row["numero_movimenti"],
            "ultima_data": row["ultima_data"],
        }
        for row in grouped.values()
    ]
    rows.sort(key=lambda row: (-row["spesa_totale"], row["label"].casefold()))
    return rows


def _build_period_summary(
    movements: list[MovimentoBancario],
    *,
    start_date: date,
    end_date: date,
    label: str,
    period_type: str,
    is_current: bool,
    preview_limit: int,
) -> dict[str, Any]:
    return {
        "periodo": {
            "tipo": period_type,
            "label": label,
            "da": start_date.isoformat(),
            "a": end_date.isoformat(),
            "corrente": is_current,
        },
        "conteggio_movimenti": len(movements),
        "conteggio_spese": sum(1 for movement in movements if movement.importo < 0),
        "conteggio_entrate": sum(1 for movement in movements if movement.importo > 0),
        "totali": {
            "spese": _expense_total(movements),
            "entrate": _income_total(movements),
            "saldo": _net_total(movements),
        },
        "spese_per_categoria": _breakdown_by_field(movements, field_name="categoria", default_label="Senza categoria"),
        "spese_per_macrocategoria": _breakdown_by_field(
            movements,
            field_name="macrocategoria",
            default_label="Senza macrocategoria",
        ),
        "top_spese": _top_expense_previews(movements, limit=preview_limit),
        "movimenti_preview": [_serialize_movimento(movement) for movement in movements[:preview_limit]],
    }


def _parse_iso_week(week_iso: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})-W(\d{2})", week_iso)
    if match is None:
        raise ValueError("La settimana deve essere nel formato YYYY-Www, per esempio 2026-W15.")
    return int(match.group(1)), int(match.group(2))


def resolve_week_window(
    week_iso: str | None = None,
    *,
    today: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    reference_day = today or date.today()
    if (start_date is None) != (end_date is None):
        raise ValueError("Per una finestra custom servono sia `start_date` sia `end_date`.")

    if start_date is not None and end_date is not None:
        if end_date < start_date:
            raise ValueError("La data finale della finestra custom non puo' precedere la data iniziale.")
        return {
            "label": label or f"{start_date.isoformat()}->{end_date.isoformat()}",
            "start_date": start_date,
            "end_date": end_date,
            "is_current": start_date <= reference_day <= end_date,
        }

    if week_iso is None:
        frontend_window = get_default_frontend_week_window(today=reference_day)
        if frontend_window is not None:
            return frontend_window
        iso_year, iso_week, _ = reference_day.isocalendar()
        week_start = reference_day - timedelta(days=reference_day.weekday())
        return {
            "label": f"{iso_year}-W{iso_week:02d}",
            "start_date": week_start,
            "end_date": reference_day,
            "is_current": True,
        }

    iso_year, iso_week = _parse_iso_week(week_iso)
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    return {
        "label": f"{iso_year}-W{iso_week:02d}",
        "start_date": week_start,
        "end_date": week_start + timedelta(days=6),
        "is_current": False,
    }


def resolve_month_window(month: str | None = None, *, today: date | None = None) -> dict[str, Any]:
    reference_day = today or date.today()
    if month is None:
        month_start = reference_day.replace(day=1)
        return {
            "label": month_start.strftime("%Y-%m"),
            "start_date": month_start,
            "end_date": reference_day,
            "is_current": True,
        }

    match = re.fullmatch(r"(\d{4})-(\d{2})", month)
    if match is None:
        raise ValueError("Il mese deve essere nel formato YYYY-MM, per esempio 2026-04.")

    year = int(match.group(1))
    month_number = int(match.group(2))
    if month_number < 1 or month_number > 12:
        raise ValueError("Il mese deve essere compreso tra 01 e 12.")

    last_day = monthrange(year, month_number)[1]
    start_date = date(year, month_number, 1)
    return {
        "label": f"{year:04d}-{month_number:02d}",
        "start_date": start_date,
        "end_date": date(year, month_number, last_day),
        "is_current": False,
    }


def _fetch_all_movements(
    session: Any,
    *,
    user_id: int | None = None,
) -> list[MovimentoBancario]:
    statement = _scope_movement_statement(
        select(MovimentoBancario).order_by(
            MovimentoBancario.data.desc(),
            MovimentoBancario.descrizione.asc(),
            MovimentoBancario.importo.asc(),
        ),
        user_id=user_id,
    )
    return list(session.exec(statement))


def _fixed_expense_rows_for_month(
    movements: list[MovimentoBancario],
    *,
    start_date: date,
    end_date: date,
    month_label: str,
    preview_limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for movement in movements:
        if movement.importo >= 0 or movement.macrocategoria != MacroCategoriaSpesa.SPESE_FISSE.value:
            continue
        if movement.data < start_date or movement.data > end_date:
            continue

        canonical_key = _canonical_description(movement.descrizione)
        amount = abs(float(movement.importo))
        current = grouped.get(canonical_key)

        if current is None:
            grouped[canonical_key] = {
                "chiave": canonical_key,
                "descrizione": movement.descrizione,
                "categoria": movement.categoria,
                "totale_mese": amount,
                "numero_movimenti": 1,
                "ultima_data": movement.data.isoformat(),
                "ultimo_importo": amount,
            }
            continue

        current["totale_mese"] += amount
        current["numero_movimenti"] += 1
        if movement.data.isoformat() > current["ultima_data"]:
            current["descrizione"] = movement.descrizione
            current["categoria"] = movement.categoria
            current["ultima_data"] = movement.data.isoformat()
            current["ultimo_importo"] = amount

    rows = []
    for current in grouped.values():
        total_month = _round_money(float(current["totale_mese"])) or 0.0
        rows.append(
            {
                "chiave": current["chiave"],
                "descrizione": current["descrizione"],
                "categoria": current["categoria"],
                "mese_riferimento": month_label,
                "spesa_totale_mese_riferimento": total_month,
                "media_mensile_sui_mesi_disponibili": total_month,
                "media_mensile_quando_presente": total_month,
                "totale_periodo": total_month,
                "mesi_presenti": [month_label],
                "mesi_presenti_count": 1,
                "numero_movimenti": current["numero_movimenti"],
                "ultima_data": current["ultima_data"],
                "ultimo_importo": _round_money(float(current["ultimo_importo"])) or 0.0,
            }
        )

    rows.sort(
        key=lambda row: (
            -(row["spesa_totale_mese_riferimento"] or 0.0),
            row["descrizione"].casefold(),
        )
    )
    return rows[:preview_limit]


def _fetch_movements_between(
    session: Any,
    *,
    start_date: date,
    end_date: date,
    user_id: int | None = None,
) -> list[MovimentoBancario]:
    statement = _scope_movement_statement(
        select(MovimentoBancario)
        .where(MovimentoBancario.data >= start_date)
        .where(MovimentoBancario.data <= end_date)
        .order_by(MovimentoBancario.data.desc(), MovimentoBancario.descrizione.asc(), MovimentoBancario.importo.asc()),
        user_id=user_id,
    )
    return list(session.exec(statement))


def _group_expense_totals_by_month(movements: list[MovimentoBancario]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for movement in movements:
        if movement.importo >= 0:
            continue
        bucket = _month_bucket(movement.data)
        totals[bucket] = totals.get(bucket, 0.0) + abs(float(movement.importo))
    return totals


def _group_expense_totals_by_week(movements: list[MovimentoBancario]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for movement in movements:
        if movement.importo >= 0:
            continue
        bucket = _week_bucket(movement.data)
        totals[bucket] = totals.get(bucket, 0.0) + abs(float(movement.importo))
    return totals


def _complete_month_labels_before(reference_start: date, movements: list[MovimentoBancario]) -> list[str]:
    return sorted({_month_bucket(movement.data) for movement in movements if movement.data < reference_start})


def _previous_complete_week_labels(target_label: str, movements: list[MovimentoBancario]) -> list[str]:
    return sorted(label for label in _group_expense_totals_by_week(movements) if label < target_label)


def _historical_average(values: list[float]) -> float | None:
    if not values:
        return None
    return _round_money(sum(values) / len(values))


def _serialize_comparison(current_total: float, historical_values: list[float]) -> dict[str, Any]:
    historical_average = _historical_average(historical_values)
    delta = None if historical_average is None else _round_money(current_total - historical_average)
    return {
        "media_storica": historical_average,
        "delta_vs_media": delta,
        "campioni": len(historical_values),
    }


def _build_recurring_item_breakdown(
    movements: list[MovimentoBancario],
    *,
    threshold: float,
    preview_limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for movement in movements:
        if movement.importo >= 0:
            continue
        canonical_key = _canonical_description(movement.descrizione)
        amount = abs(float(movement.importo))
        month_key = _month_bucket(movement.data)
        current = grouped.get(canonical_key)

        if current is None:
            grouped[canonical_key] = {
                "chiave": canonical_key,
                "descrizione": movement.descrizione,
                "categoria": movement.categoria,
                "macrocategoria": movement.macrocategoria,
                "spesa_totale": amount,
                "numero_movimenti": 1,
                "mesi_presenti": {month_key},
                "ultima_data": movement.data.isoformat(),
                "ultimo_importo": abs(float(movement.importo)),
            }
            continue

        current["spesa_totale"] += amount
        current["numero_movimenti"] += 1
        current["mesi_presenti"].add(month_key)
        if movement.data.isoformat() > current["ultima_data"]:
            current["descrizione"] = movement.descrizione
            current["categoria"] = movement.categoria
            current["macrocategoria"] = movement.macrocategoria
            current["ultima_data"] = movement.data.isoformat()
            current["ultimo_importo"] = abs(float(movement.importo))

    rows = []
    for row in grouped.values():
        spesa_totale = _round_money(float(row["spesa_totale"])) or 0.0
        mesi_presenti = sorted(row["mesi_presenti"])
        recurring = len(mesi_presenti) >= 2 or row["numero_movimenti"] >= 2
        if not recurring and spesa_totale < threshold:
            continue
        rows.append(
            {
                "chiave": row["chiave"],
                "descrizione": row["descrizione"],
                "categoria": row["categoria"],
                "macrocategoria": row["macrocategoria"],
                "spesa_totale": spesa_totale,
                "numero_movimenti": row["numero_movimenti"],
                "mesi_presenti": mesi_presenti,
                "mesi_presenti_count": len(mesi_presenti),
                "ultima_data": row["ultima_data"],
                "ultimo_importo": _round_money(float(row["ultimo_importo"])) or 0.0,
                "da_rivedere": recurring or spesa_totale >= threshold,
            }
        )

    rows.sort(key=lambda row: (-row["spesa_totale"], row["descrizione"].casefold()))
    return rows[:preview_limit]


def build_fixed_expense_monthly_summary(
    movements: list[MovimentoBancario],
    *,
    reference_date: date | None = None,
    preview_limit: int = 10,
) -> dict[str, Any]:
    today = reference_date or date.today()
    current_month_start = today.replace(day=1)
    previous_complete_month = _previous_complete_month_window(reference_date=today)
    previous_month_label = str(previous_complete_month["label"])
    previous_month_start = previous_complete_month["start_date"]
    previous_month_end = previous_complete_month["end_date"]
    complete_months = _complete_month_labels_before(current_month_start, movements)
    fixed_movements = [
        movement
        for movement in movements
        if movement.importo < 0 and movement.macrocategoria == MacroCategoriaSpesa.SPESE_FISSE.value
    ]
    current_month_total = _expense_total([movement for movement in fixed_movements if movement.data >= current_month_start])

    if previous_month_label not in complete_months:
        return {
            "mese_riferimento": previous_month_label,
            "mesi_completi_disponibili": complete_months,
            "spese_fisse_mensili_stimate": None,
            "spese_fisse_mese_corrente": current_month_total,
            "dettaglio_voci": [],
            "message": (
                "Il mese completo precedente non e' disponibile nel dataset: "
                "posso mostrarti solo il mese corrente."
            ),
        }

    reference_month_movements = [
        movement
        for movement in fixed_movements
        if previous_month_start <= movement.data <= previous_month_end
    ]
    rows = _fixed_expense_rows_for_month(
        reference_month_movements,
        start_date=previous_month_start,
        end_date=previous_month_end,
        month_label=previous_month_label,
        preview_limit=preview_limit,
    )

    total_estimated = _expense_total(reference_month_movements)

    return {
        "mese_riferimento": previous_month_label,
        "mesi_completi_disponibili": complete_months,
        "spese_fisse_mensili_stimate": total_estimated,
        "spese_fisse_mese_corrente": current_month_total,
        "dettaglio_voci": rows,
        "message": "Le spese fisse mensili usano `macrocategoria = Spese Fisse` del mese completo precedente.",
    }


def summarize_total_dataset(
    movements: list[MovimentoBancario],
    *,
    preview_limit: int,
) -> dict[str, Any]:
    if not movements:
        today = date.today()
        return _build_period_summary(
            [],
            start_date=today,
            end_date=today,
            label="dataset_vuoto",
            period_type="totale",
            is_current=True,
            preview_limit=preview_limit,
        )

    start_date = min(movement.data for movement in movements)
    end_date = max(movement.data for movement in movements)
    payload = _build_period_summary(
        movements,
        start_date=start_date,
        end_date=end_date,
        label="intero_dataset",
        period_type="totale",
        is_current=False,
        preview_limit=preview_limit,
    )
    payload["serie_mensile_spese"] = [
        {"mese": month, "spese": _round_money(total) or 0.0}
        for month, total in sorted(_group_expense_totals_by_month(movements).items())
    ]
    payload["serie_settimanale_spese"] = [
        {"settimana": week, "spese": _round_money(total) or 0.0}
        for week, total in sorted(_group_expense_totals_by_week(movements).items())
    ]
    return payload


def filter_movements_by_categories(
    movements: list[MovimentoBancario],
    *,
    categories: list[str],
) -> list[MovimentoBancario]:
    requested = set(categories)
    return [movement for movement in movements if movement.categoria in requested]


def build_goal_insight_payload(
    *,
    profile: Utente,
    period_summary: dict[str, Any],
    fixed_expense_summary: dict[str, Any],
    preview_limit: int,
) -> dict[str, Any]:
    goal_missing = not bool((profile.obiettivo or "").strip())
    spese_irrinunciabili_text = _normalize_text(profile.spese_irrinunciabili)
    category_rows = list(period_summary.get("spese_per_categoria", []))
    focus_categories = [
        row
        for row in category_rows
        if _normalize_text(row["label"]) not in spese_irrinunciabili_text
    ][:preview_limit]

    period_type = period_summary["periodo"]["tipo"]
    budget_limit = profile.disponibile_settimanale if period_type == "settimana" else profile.disponibile_mensile
    spent = period_summary["totali"].get("spese_variabili", period_summary["totali"]["spese"])
    remaining = None if budget_limit is None else _round_money(budget_limit - spent)

    if goal_missing:
        stato = "obiettivo_mancante"
    elif remaining is None:
        stato = "contesto_incompleto"
    elif remaining < 0:
        stato = "fuori_rotta"
    elif budget_limit is not None and remaining <= (budget_limit * 0.2):
        stato = "a_rischio"
    else:
        stato = "in_linea"

    alerts: list[str] = []
    if goal_missing:
        alerts.append("Manca un obiettivo salvato nel profilo: l'insight puo' solo descrivere la traiettoria, non l'arrivo.")
    if remaining is None:
        alerts.append("Il budget disponibile non e' calcolabile: manca stipendio o stima affidabile delle spese fisse essenziali.")
    elif remaining < 0:
        alerts.append("Hai gia' superato il margine disponibile per questo periodo.")
    elif budget_limit is not None and remaining <= (budget_limit * 0.2):
        alerts.append("Il margine residuo e' sotto il 20% del budget disponibile.")
    if fixed_expense_summary.get("spese_fisse_mensili_stimate") is not None and profile.stipendio_mensile:
        fixed_share = (fixed_expense_summary["spese_fisse_mensili_stimate"] / profile.stipendio_mensile) * 100
        if fixed_share >= 60:
            alerts.append("Le spese fisse da macrocategoria assorbono una quota molto alta dello stipendio.")

    actions: list[str] = []
    if focus_categories:
        top_category = focus_categories[0]
        actions.append(f"Controlla prima `{top_category['label']}`: e' la categoria che pesa di piu' in questo periodo.")
    if remaining is not None and remaining < 0:
        actions.append("Blocca le spese variabili non urgenti fino al prossimo reset di periodo.")
    elif remaining is not None and budget_limit is not None:
        actions.append(f"Per restare in linea, tieni il residuo entro {remaining} euro per il resto del periodo.")
    if fixed_expense_summary.get("dettaglio_voci"):
        actions.append(
            "Rivedi almeno una voce fissa ricorrente da macrocategoria se vuoi creare margine strutturale, non solo tattico."
        )

    return {
        "obiettivo": profile.obiettivo,
        "spese_irrinunciabili": profile.spese_irrinunciabili,
        "stato_obiettivo": stato,
        "budget_periodo": {
            "disponibile": _round_money(budget_limit),
            "speso": spent,
            "residuo": remaining,
        },
        "categorie_focus": focus_categories,
        "alerts": alerts,
        "azioni_prioritarie": actions[:preview_limit],
    }


__all__ = [
    "_breakdown_by_field",
    "_build_period_summary",
    "_canonical_description",
    "_deduplicate_movimenti",
    "_ensure_estimated_fixed_expenses",
    "_fetch_all_movements",
    "_fetch_movements_between",
    "_get_or_create_user_profile",
    "_inject_profile_context",
    "_is_likely_essential_fixed",
    "_merge_notes",
    "_profile_missing_fields",
    "_round_money",
    "_rows_to_json",
    "_serialize_expense_preview",
    "_serialize_movimento",
    "_serialize_profile",
    "_sync_budget_fields",
    "_top_expense_previews",
    "_week_bucket",
    "build_fixed_expense_context",
    "build_fixed_expense_monthly_summary",
    "build_fixed_expense_scope_payload",
    "build_goal_insight_payload",
    "filter_movements_by_categories",
    "resolve_month_window",
    "resolve_week_window",
    "summarize_total_dataset",
]
