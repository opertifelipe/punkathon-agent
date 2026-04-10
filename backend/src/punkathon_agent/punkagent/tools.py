from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta
from typing import Any

from openai import AuthenticationError
from sqlalchemy import func as sql_func
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select

from punkathon_agent.db import create_database, engine, get_session
from punkathon_agent.models.agent import (
    AggregazioneQuerySQL,
    FiltroCancellazione,
    FiltroQuerySQL,
    MovimentoInput,
    ProfiloUtenteUpdate,
    RichiestaAnalisiCategorieSpesa,
    RichiestaAnalisiMese,
    RichiestaAnalisiPerCategoria,
    RichiestaAnalisiSettimana,
    RichiestaAnalisiStorica,
    RichiestaCostruzioneQuerySQL,
    RichiestaInsightObiettivo,
    RisparmioInternoUpdate,
)
from punkathon_agent.models.db import MovimentoBancario
from punkathon_agent.models.finance import MacroCategoriaSpesa, serialize_classification_schema
from punkathon_agent.punkagent.request_context import get_current_user_id, mark_db_updated
from punkathon_agent.services.classification import classifica_movimenti
from punkathon_agent.services.spending import (
    _build_period_summary,
    _canonical_description,
    _deduplicate_movimenti,
    _ensure_estimated_fixed_expenses,
    _fetch_all_movements,
    _fetch_movements_between,
    _get_or_create_user_profile,
    _infer_essential_fixed_expense_items,
    _is_likely_essential_fixed,
    _merge_notes,
    _month_bucket,
    _profile_missing_fields,
    _round_money,
    _rows_to_json,
    _serialize_movimento,
    _serialize_profile,
    _sync_budget_fields,
    _top_expense_previews,
    _week_bucket,
    build_fixed_expense_scope_payload,
    build_fixed_expense_monthly_summary,
    build_goal_insight_payload,
    filter_movements_by_categories,
    resolve_month_window,
    resolve_week_window,
    summarize_total_dataset,
)

from .constants import MAX_QUERY_ROWS

TABLE_SCHEMAS: dict[str, dict[str, str]] = {
    "movimenti_bancari": {
        "id": "number",
        "user_id": "number",
        "data": "date",
        "descrizione": "string",
        "importo": "number",
        "note": "string",
        "categoria": "string",
        "macrocategoria": "string",
    },
    "utente": {
        "user_id": "number",
        "stipendio_mensile": "number",
        "spese_fisse_essenziali_mensili": "number",
        "disponibile_mensile": "number",
        "disponibile_settimanale": "number",
        "obiettivo": "string",
        "spese_irrinunciabili": "string",
    },
}
MOVIMENTI_BANCARI_COLUMNS = list(TABLE_SCHEMAS["movimenti_bancari"])
UTENTE_COLUMNS = list(TABLE_SCHEMAS["utente"])
SQL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TEXT_FILTER_OPERATORS = {"contains", "starts_with", "ends_with"}
NUMERIC_AGGREGATIONS = {"sum", "avg"}


def _require_current_user_id() -> int:
    current_user_id = get_current_user_id()
    if current_user_id is None:
        raise RuntimeError("Contesto utente mancante.")
    return current_user_id


def _find_exact_movement(
    session: Any,
    *,
    user_id: int,
    data: date,
    descrizione: str,
    importo: float,
) -> MovimentoBancario | None:
    statement = (
        select(MovimentoBancario)
        .where(MovimentoBancario.user_id == user_id)
        .where(MovimentoBancario.data == data)
        .where(MovimentoBancario.descrizione == descrizione)
        .where(MovimentoBancario.importo == importo)
    )
    return session.exec(statement).first()


def _is_variable_expense(movement: MovimentoBancario, inferred_descriptions: set[str]) -> bool:
    if movement.importo >= 0:
        return False
    if movement.macrocategoria == MacroCategoriaSpesa.SPESE_VARIABILI.value:
        return True
    if movement.macrocategoria == MacroCategoriaSpesa.SPESE_FISSE.value:
        return False
    return not _is_likely_essential_fixed(movement, inferred_descriptions)


def _variable_expense_total(movements: list[MovimentoBancario], inferred_descriptions: set[str]) -> float:
    return _round_money(
        sum(abs(movement.importo) for movement in movements if _is_variable_expense(movement, inferred_descriptions))
    ) or 0.0


def _prepare_profile(session: Any) -> tuple[Any, str, list[dict[str, Any]], set[str]]:
    profile = _get_or_create_user_profile(session)
    inferred_evidence = _infer_essential_fixed_expense_items(session)
    evidence, fixed_expenses_status, _ = _ensure_estimated_fixed_expenses(
        session,
        profile,
        overwrite_existing=True,
    )
    _sync_budget_fields(profile)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    inferred_descriptions = {item["chiave"] for item in inferred_evidence}
    return profile, fixed_expenses_status, evidence, inferred_descriptions


def _comparison_payload(current_total: float, historical_values: list[float]) -> dict[str, Any]:
    if not historical_values:
        return {
            "media_storica": None,
            "delta_vs_media": None,
            "campioni": 0,
        }
    historical_average = _round_money(sum(historical_values) / len(historical_values))
    return {
        "media_storica": historical_average,
        "delta_vs_media": _round_money(current_total - (historical_average or 0.0)),
        "campioni": len(historical_values),
    }


def _previous_period_values(
    totals_by_period: dict[str, float],
    *,
    current_label: str,
    limit: int,
) -> list[float]:
    labels = sorted(label for label in totals_by_period if label < current_label)
    return [totals_by_period[label] for label in labels[-limit:]]


def _previous_fixed_window_values(
    movements: list[MovimentoBancario],
    *,
    start_date: date,
    end_date: date,
    limit: int,
) -> list[float]:
    window_days = (end_date - start_date).days
    values: list[float] = []
    cursor_end = start_date - timedelta(days=1)

    for _ in range(limit):
        previous_end = cursor_end
        previous_start = previous_end - timedelta(days=window_days)
        previous_movements = [
            movement
            for movement in movements
            if movement.importo < 0 and previous_start <= movement.data <= previous_end
        ]
        if previous_movements:
            values.append(_round_money(sum(abs(movement.importo) for movement in previous_movements)) or 0.0)
        cursor_end = previous_start - timedelta(days=1)

    values.reverse()
    return values


def _expense_totals_by_month(movements: list[MovimentoBancario]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for movement in movements:
        if movement.importo >= 0:
            continue
        bucket = _month_bucket(movement.data)
        totals[bucket] = totals.get(bucket, 0.0) + abs(float(movement.importo))
    return totals


def _expense_totals_by_week(movements: list[MovimentoBancario]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for movement in movements:
        if movement.importo >= 0:
            continue
        bucket = _week_bucket(movement.data)
        totals[bucket] = totals.get(bucket, 0.0) + abs(float(movement.importo))
    return totals


def _budget_payload(
    profile: Any,
    *,
    period_type: str,
    variable_expenses: float,
) -> dict[str, Any]:
    budget_limit = profile.disponibile_settimanale if period_type == "settimana" else profile.disponibile_mensile
    if budget_limit is None:
        return {
            "budget_disponibile": None,
            "spese_variabili": variable_expenses,
            "residuo_budget": None,
            "delta_vs_budget": None,
        }

    return {
        "budget_disponibile": _round_money(budget_limit),
        "spese_variabili": variable_expenses,
        "residuo_budget": _round_money(budget_limit - variable_expenses),
        "delta_vs_budget": _round_money(variable_expenses - budget_limit),
    }


def _recurring_items(
    movements: list[MovimentoBancario],
    *,
    threshold: float,
    preview_limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for movement in movements:
        if movement.importo >= 0:
            continue
        key = (movement.categoria or "Senza categoria", _canonical_description(movement.descrizione))
        current = grouped.get(key)
        amount = abs(float(movement.importo))
        month_key = _month_bucket(movement.data)

        if current is None:
            grouped[key] = {
                "categoria": movement.categoria,
                "descrizione": movement.descrizione,
                "chiave": key[1],
                "spesa_totale": amount,
                "numero_movimenti": 1,
                "mesi_presenti": {month_key},
                "ultima_data": movement.data.isoformat(),
                "ultimo_importo": amount,
            }
            continue

        current["spesa_totale"] += amount
        current["numero_movimenti"] += 1
        current["mesi_presenti"].add(month_key)
        if movement.data.isoformat() > current["ultima_data"]:
            current["descrizione"] = movement.descrizione
            current["ultima_data"] = movement.data.isoformat()
            current["ultimo_importo"] = amount

    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        spesa_totale = _round_money(float(row["spesa_totale"])) or 0.0
        mesi_presenti = sorted(row["mesi_presenti"])
        recurring = len(mesi_presenti) >= 2 or row["numero_movimenti"] >= 2
        if not recurring and spesa_totale < threshold:
            continue
        rows.append(
            {
                "categoria": row["categoria"],
                "descrizione": row["descrizione"],
                "chiave": row["chiave"],
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


def aggiungi_movimenti(movimenti: list[MovimentoInput]) -> str:
    """Aggiunge uno o piu' movimenti alla tabella movimenti_bancari."""
    create_database()
    current_user_id = _require_current_user_id()
    added_rows: list[dict[str, Any]] = []
    merged_exact_duplicates: list[dict[str, Any]] = []
    processed_rows: list[dict[str, Any]] = []

    with get_session() as session:
        prepared_rows: list[dict[str, Any]] = []
        for movimento in movimenti:
            existing = _find_exact_movement(
                session,
                user_id=current_user_id,
                data=movimento.data,
                descrizione=movimento.descrizione,
                importo=movimento.importo,
            )
            note = _merge_notes(existing.note, movimento.note) if existing is not None else movimento.note
            prepared_rows.append(
                {
                    "movimento": movimento,
                    "existing": existing,
                    "descrizione": movimento.descrizione,
                    "importo": movimento.importo,
                    "note": note,
                }
            )

        try:
            classificazioni = classifica_movimenti(
                [
                    {
                        "descrizione": item["descrizione"],
                        "note": item["note"],
                        "importo": item["importo"],
                    }
                    for item in prepared_rows
                ]
            )
        except AuthenticationError as exc:
            raise RuntimeError(
                "Autenticazione OpenAI fallita: verifica che OPENAI_API_KEY sia presente e valida nell'ambiente corrente."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                "Non sono riuscito a classificare automaticamente i movimenti prima del salvataggio."
            ) from exc

        for item, classificazione in zip(prepared_rows, classificazioni, strict=True):
            movimento = item["movimento"]
            existing = item["existing"]
            categoria = classificazione.categoria.value
            macrocategoria = classificazione.macrocategoria.value

            if existing is not None:
                existing.note = item["note"]
                existing.categoria = categoria
                existing.macrocategoria = macrocategoria
                session.add(existing)
                serialized = _serialize_movimento(existing)
                merged_exact_duplicates.append(serialized)
                processed_rows.append(serialized)
                continue

            record_payload = movimento.model_dump()
            record_payload["user_id"] = current_user_id
            record_payload["note"] = item["note"]
            record = MovimentoBancario(
                **record_payload,
                categoria=categoria,
                macrocategoria=macrocategoria,
            )
            session.add(record)
            serialized = _serialize_movimento(record)
            added_rows.append(serialized)
            processed_rows.append(serialized)

        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError("Non sono riuscito a salvare i movimenti richiesti nel database.") from exc

        mark_db_updated()

        removed_cross_source_duplicates, remaining_cross_source_candidates = _deduplicate_movimenti(session)

    return json.dumps(
        {
            "message": "Movimenti salvati e tabella deduplicata.",
            "rows": processed_rows,
            "aggiunti": len(added_rows),
            "duplicati_esatti_gestiti": len(merged_exact_duplicates),
            "duplicati_cross_source_rimossi": len(removed_cross_source_duplicates),
            "duplicati_esatti": merged_exact_duplicates,
            "duplicati_cross_source_rimossi_dettaglio": removed_cross_source_duplicates,
            "possibili_duplicati_cross_source_residui": remaining_cross_source_candidates,
        },
        ensure_ascii=False,
        indent=2,
    )


def _schema_for_table(table_name: str) -> dict[str, str]:
    schema = TABLE_SCHEMAS.get(table_name)
    if schema is None:
        available_tables = ", ".join(sorted(TABLE_SCHEMAS))
        raise ValueError(f"Tabella non supportata: {table_name}. Tabelle disponibili: {available_tables}.")
    return schema


def _validate_column_name(table_name: str, column_name: str) -> str:
    schema = _schema_for_table(table_name)
    if column_name not in schema:
        available_columns = ", ".join(schema)
        raise ValueError(
            f"Colonna non valida per {table_name}: {column_name}. Colonne disponibili: {available_columns}."
        )
    return column_name


def _validate_sql_alias(alias: str) -> str:
    if not SQL_IDENTIFIER_PATTERN.fullmatch(alias):
        raise ValueError(
            "Alias non valido. Usa solo lettere, numeri e underscore, senza spazi, e non iniziare con un numero."
        )
    return alias


def _quote_sql_literal(value: Any, *, column_type: str) -> str:
    if column_type == "date":
        parsed_date = value if isinstance(value, date) else date.fromisoformat(str(value))
        return f"'{parsed_date.isoformat()}'"

    if column_type == "number":
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("I valori numerici devono essere finiti.")
        if numeric_value.is_integer():
            return str(int(numeric_value))
        return str(numeric_value)

    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _escape_like_pattern(value: Any) -> str:
    escaped = str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("'", "''")
    return escaped


def _semantic_description_query_guidance() -> str:
    return json.dumps(
        {
            "error": "Filtro semantico su descrizione non consentito via SQL.",
            "details": (
                "Non usare LIKE/contains sulla colonna descrizione per richieste del tipo "
                "'ho speso per pizza questo mese?'."
            ),
            "suggested_tool": "ottieni_movimenti_mese_corrente",
            "alternative_tools": [
                "ottieni_movimenti_mese_corrente",
                "analizza_spese_mese",
                "analizza_spese_per_categoria",
            ],
            "hint": (
                "Se la richiesta riguarda questo mese, chiama `ottieni_movimenti_mese_corrente` "
                "e fai matching semantico sulle descrizioni restituite; per categorie esplicite usa "
                "`analizza_spese_per_categoria`."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def _build_where_clause(table_name: str, filtro: FiltroQuerySQL) -> str:
    column_name = _validate_column_name(table_name, filtro.colonna)
    column_type = _schema_for_table(table_name)[column_name]
    operator = filtro.operatore

    if table_name == "movimenti_bancari" and column_name == "descrizione" and operator in TEXT_FILTER_OPERATORS:
        raise ValueError(
            "Non usare filtri LIKE/contains su `descrizione`. Per domande semantiche usa gli strumenti di analisi dedicati."
        )

    if operator in {"is_null", "is_not_null"}:
        keyword = "IS NULL" if operator == "is_null" else "IS NOT NULL"
        return f"{column_name} {keyword}"

    if operator in TEXT_FILTER_OPERATORS:
        if column_type != "string":
            raise ValueError(f"L'operatore {operator} e' valido solo per colonne stringa.")
        if filtro.valore is None:
            raise ValueError(f"L'operatore {operator} richiede un valore.")

        pattern = _escape_like_pattern(filtro.valore)
        if operator == "contains":
            return f"{column_name} LIKE '%{pattern}%' ESCAPE '\\'"
        if operator == "starts_with":
            return f"{column_name} LIKE '{pattern}%' ESCAPE '\\'"
        return f"{column_name} LIKE '%{pattern}' ESCAPE '\\'"

    if operator in {"in", "not_in"}:
        if not isinstance(filtro.valore, list) or not filtro.valore:
            raise ValueError(f"L'operatore {operator} richiede una lista non vuota di valori.")
        values_sql = ", ".join(_quote_sql_literal(item, column_type=column_type) for item in filtro.valore)
        keyword = "IN" if operator == "in" else "NOT IN"
        return f"{column_name} {keyword} ({values_sql})"

    if operator == "between":
        if filtro.valore is None or filtro.secondo_valore is None:
            raise ValueError("L'operatore `between` richiede valore e secondo_valore.")
        lower_bound = _quote_sql_literal(filtro.valore, column_type=column_type)
        upper_bound = _quote_sql_literal(filtro.secondo_valore, column_type=column_type)
        return f"{column_name} BETWEEN {lower_bound} AND {upper_bound}"

    if filtro.valore is None:
        raise ValueError(f"L'operatore {operator} richiede un valore.")

    value_sql = _quote_sql_literal(filtro.valore, column_type=column_type)
    comparison_by_operator = {
        "eq": "=",
        "neq": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
    }
    comparison = comparison_by_operator.get(operator)
    if comparison is None:
        raise ValueError(f"Operatore filtro non supportato: {operator}.")
    return f"{column_name} {comparison} {value_sql}"


def _default_aggregation_alias(aggregation: AggregazioneQuerySQL) -> str:
    column_fragment = "rows" if aggregation.colonna == "*" else aggregation.colonna
    return f"{aggregation.funzione}_{column_fragment}"


def _build_aggregation_clause(table_name: str, aggregation: AggregazioneQuerySQL) -> tuple[str, str]:
    function_name = aggregation.funzione.upper()

    if aggregation.colonna == "*":
        if aggregation.funzione != "count":
            raise ValueError("Solo COUNT supporta `*` come colonna aggregata.")
        target_sql = "*"
    else:
        column_name = _validate_column_name(table_name, aggregation.colonna)
        column_type = _schema_for_table(table_name)[column_name]
        if aggregation.funzione in NUMERIC_AGGREGATIONS and column_type != "number":
            raise ValueError(
                f"L'aggregazione {aggregation.funzione} richiede una colonna numerica, non {column_name}."
            )
        target_sql = column_name

    alias = _validate_sql_alias(aggregation.alias or _default_aggregation_alias(aggregation))
    return f"{function_name}({target_sql}) AS {alias}", alias


def costruisci_query_sql(payload: RichiestaCostruzioneQuerySQL) -> str:
    """Costruisce una query SELECT valida usando solo tabelle e colonne presenti nello schema noto."""
    create_database()

    table_name = payload.tabella
    table_schema = _schema_for_table(table_name)
    selected_columns = list(dict.fromkeys(payload.colonne))
    group_by_columns = list(dict.fromkeys(payload.group_by))

    if payload.aggregazioni and group_by_columns:
        for column_name in reversed(group_by_columns):
            if column_name not in selected_columns:
                selected_columns.insert(0, column_name)

    if not selected_columns and not payload.aggregazioni:
        selected_columns = list(table_schema)

    if payload.aggregazioni:
        invalid_grouping_columns = [column_name for column_name in selected_columns if column_name not in group_by_columns]
        if invalid_grouping_columns:
            missing_text = ", ".join(invalid_grouping_columns)
            raise ValueError(
                f"Con aggregazioni attive, le colonne selezionate devono comparire in group_by. Mancano: {missing_text}."
            )

    select_fragments = [_validate_column_name(table_name, column_name) for column_name in selected_columns]
    aggregation_aliases: set[str] = set()
    aggregation_payloads: list[dict[str, str]] = []
    for aggregation in payload.aggregazioni:
        fragment, alias = _build_aggregation_clause(table_name, aggregation)
        aggregation_aliases.add(alias)
        aggregation_payloads.append(
            {
                "funzione": aggregation.funzione,
                "colonna": aggregation.colonna,
                "alias": alias,
            }
        )
        select_fragments.append(fragment)

    if not select_fragments:
        raise ValueError("La query deve selezionare almeno una colonna o un'aggregazione.")

    sql_parts = [f"SELECT {'DISTINCT ' if payload.distinct else ''}{', '.join(select_fragments)}", f"FROM {table_name}"]

    if payload.filtri:
        filter_parts: list[str] = []
        try:
            for index, filtro in enumerate(payload.filtri):
                clause = _build_where_clause(table_name, filtro)
                if index == 0:
                    filter_parts.append(clause)
                    continue
                filter_parts.append(f"{filtro.combina_con_precedente.upper()} {clause}")
        except ValueError as exc:
            if "LIKE/contains" in str(exc) and "descrizione" in str(exc):
                return _semantic_description_query_guidance()
            raise
        sql_parts.append(f"WHERE {' '.join(filter_parts)}")

    if group_by_columns:
        validated_group_by = [_validate_column_name(table_name, column_name) for column_name in group_by_columns]
        sql_parts.append(f"GROUP BY {', '.join(validated_group_by)}")

    if payload.order_by:
        order_fragments: list[str] = []
        allowed_order_targets = set(table_schema) | aggregation_aliases
        for order_item in payload.order_by:
            if order_item.campo in aggregation_aliases:
                order_target = order_item.campo
            else:
                order_target = _validate_column_name(table_name, order_item.campo)
            if order_target not in allowed_order_targets:
                raise ValueError(f"Campo non valido per ORDER BY: {order_item.campo}.")
            order_fragments.append(f"{order_target} {order_item.direzione.upper()}")
        sql_parts.append(f"ORDER BY {', '.join(order_fragments)}")

    if payload.limit is not None:
        sql_parts.append(f"LIMIT {payload.limit}")

    sql = " ".join(sql_parts)
    return json.dumps(
        {
            "sql": sql,
            "tabella": table_name,
            "schema_tabella": table_schema,
            "colonne_selezionate": selected_columns,
            "aggregazioni": aggregation_payloads,
            "group_by": group_by_columns,
            "order_by": [item.model_dump() for item in payload.order_by],
            "limit": payload.limit,
            "message": "Passa il valore del campo `sql` al tool `esegui_query_sql` per eseguire la query sul database.",
        },
        ensure_ascii=False,
        indent=2,
    )


def _period_window_for_category_request(
    payload: RichiestaAnalisiPerCategoria,
    *,
    all_movements: list[MovimentoBancario],
) -> tuple[dict[str, Any], list[MovimentoBancario]]:
    if payload.periodo == "settimana":
        window = resolve_week_window(
            payload.settimana_iso,
            start_date=payload.data_da,
            end_date=payload.data_a,
            label=payload.label_periodo,
        )
        period_movements = [
            movement for movement in all_movements if window["start_date"] <= movement.data <= window["end_date"]
        ]
        return window, period_movements

    if payload.periodo == "mese":
        window = resolve_month_window(payload.mese)
        period_movements = [
            movement for movement in all_movements if window["start_date"] <= movement.data <= window["end_date"]
        ]
        return window, period_movements

    if not all_movements:
        today = date.today()
        window = {
            "label": "intero_dataset",
            "start_date": today,
            "end_date": today,
            "is_current": True,
        }
        return window, []

    start_date = min(movement.data for movement in all_movements)
    end_date = max(movement.data for movement in all_movements)
    window = {
        "label": "intero_dataset",
        "start_date": start_date,
        "end_date": end_date,
        "is_current": False,
    }
    return window, all_movements


def analizza_spese_per_categoria(payload: RichiestaAnalisiPerCategoria) -> str:
    """Analizza le spese per una o piu' categorie su settimana, mese o intero dataset."""
    create_database()
    requested_categories = [category.value for category in payload.categorie]

    with get_session() as session:
        profile, fixed_expenses_status, fixed_expenses_evidence, inferred_descriptions = _prepare_profile(session)
        all_movements = _fetch_all_movements(session)

    window, period_movements = _period_window_for_category_request(payload, all_movements=all_movements)
    filtered_period_movements = filter_movements_by_categories(period_movements, categories=requested_categories)
    summary = _build_period_summary(
        filtered_period_movements,
        start_date=window["start_date"],
        end_date=window["end_date"],
        label=window["label"],
        period_type=payload.periodo,
        is_current=window["is_current"],
        preview_limit=payload.preview_limit,
    )
    variable_expenses = _variable_expense_total(filtered_period_movements, inferred_descriptions)
    summary["totali"]["spese_variabili"] = variable_expenses

    detail_rows: list[dict[str, Any]] = []
    all_review_rows: list[dict[str, Any]] = []

    for category in requested_categories:
        period_rows = [movement for movement in filtered_period_movements if movement.categoria == category]
        historical_rows = [movement for movement in all_movements if movement.categoria == category]
        monthly_totals = _expense_totals_by_month(historical_rows)
        weekly_totals = _expense_totals_by_week(historical_rows)
        current_category_spend = _round_money(sum(abs(row.importo) for row in period_rows if row.importo < 0)) or 0.0

        if payload.periodo == "settimana":
            comparison = _comparison_payload(
                current_category_spend,
                _previous_fixed_window_values(
                    historical_rows,
                    start_date=window["start_date"],
                    end_date=window["end_date"],
                    limit=4,
                )
                if payload.data_da is not None or payload.settimana_iso is None
                else _previous_period_values(weekly_totals, current_label=window["label"], limit=4),
            )
        elif payload.periodo == "mese":
            comparison = _comparison_payload(
                current_category_spend,
                _previous_period_values(monthly_totals, current_label=window["label"], limit=3),
            )
        else:
            comparison = {
                "media_mensile_dataset": _round_money(sum(monthly_totals.values()) / len(monthly_totals)) if monthly_totals else None,
                "mesi_con_spesa": len(monthly_totals),
            }

        review_rows = _recurring_items(
            historical_rows,
            threshold=payload.soglia_importo_rilevante,
            preview_limit=payload.preview_limit,
        )
        all_review_rows.extend(review_rows)

        detail_rows.append(
            {
                "categoria": category,
                "spesa_periodo": current_category_spend,
                "entrate_periodo": _round_money(sum(row.importo for row in period_rows if row.importo > 0)) or 0.0,
                "numero_movimenti": len(period_rows),
                "movimenti_preview": [_serialize_movimento(row) for row in period_rows[: payload.preview_limit]],
                "top_spese": _top_expense_previews(period_rows, limit=payload.preview_limit),
                "confronto_storico": comparison,
                "voci_da_rivedere": review_rows,
            }
        )

    all_review_rows.sort(key=lambda row: (-row["spesa_totale"], row["descrizione"].casefold()))

    return json.dumps(
        {
            "profilo": _serialize_profile(profile),
            "campi_mancanti": _profile_missing_fields(profile),
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            "evidenze_spese_fisse_essenziali": fixed_expenses_evidence[: payload.preview_limit],
            "evidenze_spese_fisse": fixed_expenses_evidence[: payload.preview_limit],
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=fixed_expenses_evidence,
                preview_limit=payload.preview_limit,
            ),
            "categorie": requested_categories,
            **summary,
            "budget_categoria": _budget_payload(profile, period_type=payload.periodo, variable_expenses=variable_expenses)
            if payload.periodo in {"settimana", "mese"}
            else None,
            "dettaglio_categorie": detail_rows,
            "voci_da_rivedere": all_review_rows[: payload.preview_limit],
        },
        ensure_ascii=False,
        indent=2,
    )


def analizza_spese_settimana(payload: RichiestaAnalisiSettimana | None = None) -> str:
    """Analizza le spese di una settimana specifica; se non indicata usa la settimana corrente."""
    create_database()
    resolved_payload = payload or RichiestaAnalisiSettimana()
    window = resolve_week_window(
        resolved_payload.settimana_iso,
        start_date=resolved_payload.data_da,
        end_date=resolved_payload.data_a,
        label=resolved_payload.label_periodo,
    )

    with get_session() as session:
        profile, fixed_expenses_status, fixed_expenses_evidence, inferred_descriptions = _prepare_profile(session)
        all_movements = _fetch_all_movements(session)
        week_movements = _fetch_movements_between(
            session,
            start_date=window["start_date"],
            end_date=window["end_date"],
        )

    summary = _build_period_summary(
        week_movements,
        start_date=window["start_date"],
        end_date=window["end_date"],
        label=window["label"],
        period_type="settimana",
        is_current=window["is_current"],
        preview_limit=resolved_payload.preview_limit,
    )
    variable_expenses = _variable_expense_total(week_movements, inferred_descriptions)
    summary["totali"]["spese_variabili"] = variable_expenses
    totals_by_week = _expense_totals_by_week(all_movements)
    comparison = _comparison_payload(
        summary["totali"]["spese"],
        _previous_fixed_window_values(
            all_movements,
            start_date=window["start_date"],
            end_date=window["end_date"],
            limit=4,
        )
        if resolved_payload.data_da is not None or resolved_payload.settimana_iso is None
        else _previous_period_values(totals_by_week, current_label=window["label"], limit=4),
    )

    return json.dumps(
        {
            "profilo": _serialize_profile(profile),
            "campi_mancanti": _profile_missing_fields(profile),
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            "evidenze_spese_fisse_essenziali": fixed_expenses_evidence[: resolved_payload.preview_limit],
            "evidenze_spese_fisse": fixed_expenses_evidence[: resolved_payload.preview_limit],
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=fixed_expenses_evidence,
                preview_limit=resolved_payload.preview_limit,
            ),
            **summary,
            "confronto_settimane_precedenti": comparison,
            "budget": _budget_payload(profile, period_type="settimana", variable_expenses=variable_expenses),
        },
        ensure_ascii=False,
        indent=2,
    )


def analizza_spese_mese(payload: RichiestaAnalisiMese | None = None) -> str:
    """Analizza le spese di un mese specifico; se non indicato usa il mese corrente."""
    create_database()
    resolved_payload = payload or RichiestaAnalisiMese()
    window = resolve_month_window(resolved_payload.mese)

    with get_session() as session:
        profile, fixed_expenses_status, fixed_expenses_evidence, inferred_descriptions = _prepare_profile(session)
        all_movements = _fetch_all_movements(session)
        month_movements = _fetch_movements_between(
            session,
            start_date=window["start_date"],
            end_date=window["end_date"],
        )

    summary = _build_period_summary(
        month_movements,
        start_date=window["start_date"],
        end_date=window["end_date"],
        label=window["label"],
        period_type="mese",
        is_current=window["is_current"],
        preview_limit=resolved_payload.preview_limit,
    )
    variable_expenses = _variable_expense_total(month_movements, inferred_descriptions)
    summary["totali"]["spese_variabili"] = variable_expenses
    totals_by_month = _expense_totals_by_month(all_movements)
    comparison = _comparison_payload(
        summary["totali"]["spese"],
        _previous_period_values(totals_by_month, current_label=window["label"], limit=3),
    )

    return json.dumps(
        {
            "profilo": _serialize_profile(profile),
            "campi_mancanti": _profile_missing_fields(profile),
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            "evidenze_spese_fisse_essenziali": fixed_expenses_evidence[: resolved_payload.preview_limit],
            "evidenze_spese_fisse": fixed_expenses_evidence[: resolved_payload.preview_limit],
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=fixed_expenses_evidence,
                preview_limit=resolved_payload.preview_limit,
            ),
            **summary,
            "confronto_mesi_precedenti": comparison,
            "budget": _budget_payload(profile, period_type="mese", variable_expenses=variable_expenses),
        },
        ensure_ascii=False,
        indent=2,
    )


def analizza_spese_complessive(payload: RichiestaAnalisiStorica | None = None) -> str:
    """Analizza lo storico completo disponibile nel database."""
    create_database()
    resolved_payload = payload or RichiestaAnalisiStorica()

    with get_session() as session:
        profile, fixed_expenses_status, fixed_expenses_evidence, inferred_descriptions = _prepare_profile(session)
        all_movements = _fetch_all_movements(session)

    summary = summarize_total_dataset(all_movements, preview_limit=resolved_payload.preview_limit)
    summary["totali"]["spese_variabili"] = _variable_expense_total(all_movements, inferred_descriptions)
    fixed_summary = build_fixed_expense_monthly_summary(
        all_movements,
        preview_limit=resolved_payload.preview_limit,
    )

    monthly_series = summary.get("serie_mensile_spese", [])
    weekly_series = summary.get("serie_settimanale_spese", [])

    return json.dumps(
        {
            "profilo": _serialize_profile(profile),
            "campi_mancanti": _profile_missing_fields(profile),
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            "evidenze_spese_fisse_essenziali": fixed_expenses_evidence[: resolved_payload.preview_limit],
            "evidenze_spese_fisse": fixed_expenses_evidence[: resolved_payload.preview_limit],
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=fixed_expenses_evidence,
                preview_limit=resolved_payload.preview_limit,
                fixed_expense_summary=fixed_summary,
                include_full_macro_summary=True,
            ),
            **summary,
            "media_spese_mensili_dataset": _round_money(
                sum(item["spese"] for item in monthly_series) / len(monthly_series)
            )
            if monthly_series
            else None,
            "media_spese_settimanali_dataset": _round_money(
                sum(item["spese"] for item in weekly_series) / len(weekly_series)
            )
            if weekly_series
            else None,
            "spese_fisse_mensili": fixed_summary,
        },
        ensure_ascii=False,
        indent=2,
    )


def calcola_spese_fisse_mensili(preview_limit: int = 10) -> str:
    """Calcola le spese fisse mensili usando `macrocategoria = Spese Fisse` del mese completo precedente."""
    create_database()
    safe_preview_limit = max(1, min(int(preview_limit), 20))

    with get_session() as session:
        profile, fixed_expenses_status, fixed_expenses_evidence, _ = _prepare_profile(session)
        all_movements = _fetch_all_movements(session)

    fixed_summary = build_fixed_expense_monthly_summary(
        all_movements,
        preview_limit=safe_preview_limit,
    )

    return json.dumps(
        {
            "profilo": _serialize_profile(profile),
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            "evidenze_spese_fisse_essenziali": fixed_expenses_evidence[:safe_preview_limit],
            "evidenze_spese_fisse": fixed_expenses_evidence[:safe_preview_limit],
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=fixed_expenses_evidence,
                preview_limit=safe_preview_limit,
                fixed_expense_summary=fixed_summary,
                include_full_macro_summary=True,
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def analizza_spese_fisse(preview_limit: int = 10) -> str:
    """Alias semantico per richieste come 'dammi le spese fisse': usa `macrocategoria = Spese Fisse`."""
    return calcola_spese_fisse_mensili(preview_limit=preview_limit)


def _goal_insight_response(
    *,
    periodo: str,
    settimana_iso: str | None = None,
    data_da: date | None = None,
    data_a: date | None = None,
    label_periodo: str | None = None,
    mese: str | None = None,
    preview_limit: int,
) -> str:
    create_database()

    if periodo == "settimana":
        window = resolve_week_window(
            settimana_iso,
            start_date=data_da,
            end_date=data_a,
            label=label_periodo,
        )
    else:
        window = resolve_month_window(mese)

    with get_session() as session:
        profile, fixed_expenses_status, fixed_expenses_evidence, inferred_descriptions = _prepare_profile(session)
        all_movements = _fetch_all_movements(session)
        period_movements = _fetch_movements_between(
            session,
            start_date=window["start_date"],
            end_date=window["end_date"],
        )

    period_summary = _build_period_summary(
        period_movements,
        start_date=window["start_date"],
        end_date=window["end_date"],
        label=window["label"],
        period_type=periodo,
        is_current=window["is_current"],
        preview_limit=preview_limit,
    )
    period_summary["totali"]["spese_variabili"] = _variable_expense_total(period_movements, inferred_descriptions)
    fixed_summary = build_fixed_expense_monthly_summary(all_movements, preview_limit=preview_limit)
    insight = build_goal_insight_payload(
        profile=profile,
        period_summary=period_summary,
        fixed_expense_summary=fixed_summary,
        preview_limit=preview_limit,
    )

    return json.dumps(
        {
            "profilo": _serialize_profile(profile),
            "campi_mancanti": _profile_missing_fields(profile),
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            "evidenze_spese_fisse_essenziali": fixed_expenses_evidence[:preview_limit],
            "evidenze_spese_fisse": fixed_expenses_evidence[:preview_limit],
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=fixed_expenses_evidence,
                preview_limit=preview_limit,
                fixed_expense_summary=fixed_summary,
                include_full_macro_summary=True,
            ),
            **period_summary,
            "budget": _budget_payload(
                profile,
                period_type=periodo,
                variable_expenses=period_summary["totali"]["spese_variabili"],
            ),
            "spese_fisse_mensili": fixed_summary,
            "insight_obiettivo": insight,
        },
        ensure_ascii=False,
        indent=2,
    )


def genera_insight_settimanali(payload: RichiestaInsightObiettivo | None = None) -> str:
    """Genera insight settimanali guidati dall'obiettivo utente; se la settimana non e' definita usa quella corrente."""
    resolved_payload = payload or RichiestaInsightObiettivo(periodo="settimana")
    return _goal_insight_response(
        periodo="settimana",
        settimana_iso=resolved_payload.settimana_iso,
        data_da=resolved_payload.data_da,
        data_a=resolved_payload.data_a,
        label_periodo=resolved_payload.label_periodo,
        preview_limit=resolved_payload.preview_limit,
    )


def genera_insight_mensili(payload: RichiestaInsightObiettivo | None = None) -> str:
    """Genera insight mensili guidati dall'obiettivo utente; se il mese non e' definito usa quello corrente."""
    resolved_payload = payload or RichiestaInsightObiettivo(periodo="mese")
    return _goal_insight_response(
        periodo="mese",
        mese=resolved_payload.mese,
        preview_limit=resolved_payload.preview_limit,
    )


def aggiorna_risparmio_interno(payload: RisparmioInternoUpdate) -> str:
    """Uso interno: aggiorna il campo risparmio senza esporne mai il valore in lettura."""
    create_database()

    with get_session() as session:
        profile = _get_or_create_user_profile(session)
        profile.risparmio = _round_money(payload.risparmio)
        session.add(profile)
        session.commit()

    mark_db_updated()

    return json.dumps(
        {
            "message": "Campo risparmio aggiornato per uso interno.",
            "motivo_registrato": payload.motivo.strip(),
        },
        ensure_ascii=False,
        indent=2,
    )


def cancella_movimenti(filtro: FiltroCancellazione) -> str:
    """Cancella i movimenti che corrispondono ai filtri indicati."""
    create_database()
    statement = select(MovimentoBancario).where(MovimentoBancario.user_id == _require_current_user_id())

    if filtro.data is not None:
        statement = statement.where(MovimentoBancario.data == filtro.data)
    if filtro.data_da is not None:
        statement = statement.where(MovimentoBancario.data >= filtro.data_da)
    if filtro.data_a is not None:
        statement = statement.where(MovimentoBancario.data <= filtro.data_a)
    if filtro.descrizione_contiene:
        statement = statement.where(MovimentoBancario.descrizione.ilike(f"%{filtro.descrizione_contiene}%"))
    if filtro.importo_min is not None:
        statement = statement.where(MovimentoBancario.importo >= filtro.importo_min)
    if filtro.importo_max is not None:
        statement = statement.where(MovimentoBancario.importo <= filtro.importo_max)
    if filtro.note_contiene:
        statement = statement.where(MovimentoBancario.note.ilike(f"%{filtro.note_contiene}%"))

    with get_session() as session:
        matches = list(session.exec(statement))
        if not matches:
            return json.dumps(
                {"message": "Nessun movimento trovato con i filtri indicati.", "rows": []},
                ensure_ascii=False,
                indent=2,
            )

        deleted = [_serialize_movimento(item) for item in matches]
        for item in matches:
            session.delete(item)
        session.commit()

    mark_db_updated()

    return json.dumps(
        {
            "message": f"Cancellati {len(deleted)} movimenti.",
            "rows": deleted,
        },
        ensure_ascii=False,
        indent=2,
    )


def ottieni_profilo_utente() -> str:
    """Restituisce il profilo utente con spese fisse mensili sincronizzate dal mese completo precedente."""
    create_database()

    with get_session() as session:
        profile, fixed_expenses_status, evidence, _ = _prepare_profile(session)
        all_movements = _fetch_all_movements(session)

    fixed_summary = build_fixed_expense_monthly_summary(all_movements, preview_limit=3)

    missing_fields = _profile_missing_fields(profile)
    if "stipendio_mensile" in missing_fields:
        message = "Profilo utente incompleto: manca ancora lo stipendio mensile."
    elif fixed_expenses_status == "non_stimabili_dai_movimenti":
        message = (
            "Profilo utente parziale: non riesco ancora a calcolare le spese fisse mensili "
            "dal mese completo precedente."
        )
    elif fixed_expenses_status in {"stimate_automaticamente", "ricalcolate_automaticamente"}:
        message = (
            "Profilo utente aggiornato con spese fisse mensili sincronizzate dalla "
            "macrocategoria `Spese Fisse` del mese completo precedente."
        )
    else:
        message = "Profilo utente pronto all'uso."

    return json.dumps(
        {
            "profilo": _serialize_profile(profile),
            "campi_mancanti": missing_fields,
            "stato_spese_fisse_essenziali": fixed_expenses_status,
            "evidenze_spese_fisse_essenziali": evidence,
            "evidenze_spese_fisse": evidence,
            **build_fixed_expense_scope_payload(
                profile=profile,
                fixed_expenses_status=fixed_expenses_status,
                fixed_expenses_evidence=evidence,
                preview_limit=3,
                fixed_expense_summary=fixed_summary,
                include_full_macro_summary=False,
            ),
            "message": message,
        },
        ensure_ascii=False,
        indent=2,
    )


def aggiorna_profilo_utente(payload: ProfiloUtenteUpdate) -> str:
    """Aggiorna i campi del profilo utente e ricalcola il budget disponibile."""
    create_database()

    with get_session() as session:
        profile = _get_or_create_user_profile(session)

        if payload.stipendio_mensile is not None:
            profile.stipendio_mensile = _round_money(payload.stipendio_mensile)
        if payload.spese_fisse_essenziali_mensili is not None:
            profile.spese_fisse_essenziali_mensili = _round_money(payload.spese_fisse_essenziali_mensili)
        if payload.obiettivo is not None:
            profile.obiettivo = payload.obiettivo.strip() or None
        if payload.spese_irrinunciabili is not None:
            profile.spese_irrinunciabili = payload.spese_irrinunciabili.strip() or None

        _sync_budget_fields(profile)
        session.add(profile)
        session.commit()
        session.refresh(profile)

    mark_db_updated()

    return json.dumps(
        {
            "message": "Profilo utente aggiornato.",
            "profilo": _serialize_profile(profile),
            "campi_mancanti": _profile_missing_fields(profile),
        },
        ensure_ascii=False,
        indent=2,
    )


def stima_spese_fisse_essenziali(sovrascrivi_valore_esistente: bool = False) -> str:
    """Sincronizza nel profilo il totale `Spese Fisse` del mese completo precedente."""
    create_database()

    with get_session() as session:
        profile = _get_or_create_user_profile(session)

        if profile.spese_fisse_essenziali_mensili is not None and not sovrascrivi_valore_esistente:
            return json.dumps(
                {
                    "message": "Le spese fisse mensili sono gia' presenti nel profilo utente.",
                    "profilo": _serialize_profile(profile),
                    "evidenze": [],
                },
                ensure_ascii=False,
                indent=2,
            )

        evidence, fixed_expenses_status, changed = _ensure_estimated_fixed_expenses(
            session,
            profile,
            overwrite_existing=sovrascrivi_valore_esistente,
        )

        if fixed_expenses_status == "non_stimabili_dai_movimenti":
            return json.dumps(
                {
                    "message": (
                        "Non riesco a calcolare le spese fisse mensili dal mese completo precedente "
                        "con i movimenti disponibili in questo momento."
                    ),
                    "profilo": _serialize_profile(profile),
                    "evidenze": [],
                },
                ensure_ascii=False,
                indent=2,
            )

    if changed:
        mark_db_updated()

    return json.dumps(
        {
            "message": (
                "Ho calcolato e salvato le spese fisse mensili usando la macrocategoria "
                "`Spese Fisse` del mese completo precedente."
            ),
            "profilo": _serialize_profile(profile),
            "evidenze": evidence,
        },
        ensure_ascii=False,
        indent=2,
    )


def analizza_budget_attuale() -> str:
    """Compatibilita': restituisce il quadro del mese e della settimana correnti con focus sul budget variabile."""
    month_payload = json.loads(analizza_spese_mese())
    week_payload = json.loads(analizza_spese_settimana())

    alerts: list[str] = []
    week_budget = week_payload.get("budget") or {}
    month_budget = month_payload.get("budget") or {}

    if week_budget.get("residuo_budget") is not None and week_budget["residuo_budget"] < 0:
        alerts.append("Budget settimanale sforato.")
    if month_budget.get("residuo_budget") is not None and month_budget["residuo_budget"] < 0:
        alerts.append("Budget mensile sforato.")
    if "stipendio_mensile" in month_payload.get("campi_mancanti", []):
        alerts.append("Manca lo stipendio mensile.")

    return json.dumps(
        {
            "profilo": month_payload.get("profilo"),
            "campi_mancanti": month_payload.get("campi_mancanti", []),
            "stato_spese_fisse_essenziali": month_payload.get("stato_spese_fisse_essenziali"),
            "mese_corrente": {
                "da": month_payload["periodo"]["da"],
                "a": month_payload["periodo"]["a"],
                "entrate": month_payload["totali"]["entrate"],
                "spese_totali": month_payload["totali"]["spese"],
                "spese_variabili": month_payload["totali"].get("spese_variabili"),
                "budget_variabile_residuo": month_budget.get("residuo_budget"),
            },
            "settimana_corrente": {
                "da": week_payload["periodo"]["da"],
                "a": week_payload["periodo"]["a"],
                "spese_totali": week_payload["totali"]["spese"],
                "spese_variabili": week_payload["totali"].get("spese_variabili"),
                "budget_variabile_residuo": week_budget.get("residuo_budget"),
            },
            "top_spese_variabili": month_payload.get("top_spese", []),
            "evidenze_spese_fisse_essenziali": month_payload.get(
                "evidenze_spese_fisse_essenziali",
                month_payload.get("evidenze_spese_fisse", []),
            ),
            "evidenze_spese_fisse": month_payload.get(
                "evidenze_spese_fisse_essenziali",
                month_payload.get("evidenze_spese_fisse", []),
            ),
            "contesto_spese_fisse": month_payload.get("contesto_spese_fisse"),
            "alerts": alerts,
        },
        ensure_ascii=False,
        indent=2,
    )


def ottieni_movimenti_mese_corrente() -> str:
    """Restituisce tutti i movimenti registrati nel mese corrente, senza filtrare per parole chiave."""
    create_database()
    window = resolve_month_window(None)

    with get_session() as session:
        movements = _fetch_movements_between(
            session,
            start_date=window["start_date"],
            end_date=window["end_date"],
        )

    total_expenses = _round_money(sum(abs(movement.importo) for movement in movements if movement.importo < 0)) or 0.0
    total_income = _round_money(sum(movement.importo for movement in movements if movement.importo > 0)) or 0.0

    return json.dumps(
        {
            "periodo": {
                "da": window["start_date"].isoformat(),
                "a": window["end_date"].isoformat(),
            },
            "rows": [_serialize_movimento(movement) for movement in movements],
            "count": len(movements),
            "count_spese": sum(1 for movement in movements if movement.importo < 0),
            "count_entrate": sum(1 for movement in movements if movement.importo > 0),
            "totale_spese": total_expenses,
            "totale_entrate": total_income,
            "message": "Usa questi movimenti completi del mese corrente per letture semantiche sulle spese recenti.",
        },
        ensure_ascii=False,
        indent=2,
    )


def riepilogo_movimenti_database(limit: int = 5) -> str:
    """Restituisce conteggio totale movimenti e ultime righe del database."""
    create_database()
    current_user_id = _require_current_user_id()
    safe_limit = max(1, min(int(limit), 20))

    with get_session() as session:
        total_movements = session.exec(
            select(sql_func.count())
            .select_from(MovimentoBancario)
            .where(MovimentoBancario.user_id == current_user_id)
        ).one()
        statement = (
            select(MovimentoBancario)
            .where(MovimentoBancario.user_id == current_user_id)
            .order_by(MovimentoBancario.data.desc(), MovimentoBancario.descrizione.asc(), MovimentoBancario.importo.asc())
            .limit(safe_limit)
        )
        movements = list(session.exec(statement))

    return json.dumps(
        {
            "count": int(total_movements),
            "limit": safe_limit,
            "rows": [_serialize_movimento(movement) for movement in movements],
            "message": "Usa questo riepilogo per conteggio totale e ultime righe senza inventarti colonne che non esistono.",
        },
        ensure_ascii=False,
        indent=2,
    )


def esegui_query_sql(sql: str) -> str:
    """Esegue una query SQL di sola lettura sulle tabelle movimenti_bancari e utente."""
    create_database()
    current_user_id = _require_current_user_id()
    cleaned_sql = sql.strip().rstrip(";")
    lowered_sql = cleaned_sql.lower()

    if not cleaned_sql:
        raise ValueError("La query SQL non puo' essere vuota.")
    if ";" in cleaned_sql:
        raise ValueError("E' consentita una sola query per volta.")
    if not lowered_sql.startswith(("select", "with")):
        raise ValueError("Sono consentite solo query di lettura SELECT.")
    if "movimenti_bancari" not in lowered_sql and "utente" not in lowered_sql:
        raise ValueError("La query deve riferirsi alla tabella movimenti_bancari e/o alla tabella utente.")
    if "utente" in lowered_sql and re.search(r"\brisparmio\b", lowered_sql):
        raise ValueError("Il campo risparmio non e' leggibile dall'agente.")
    if "utente" in lowered_sql and (re.search(r"select\s+\*", lowered_sql) or "utente.*" in lowered_sql):
        raise ValueError("Per la tabella utente devi selezionare esplicitamente solo le colonne leggibili.")
    if "main." in lowered_sql or "temp." in lowered_sql:
        raise ValueError("Non usare prefissi di schema espliciti nelle query SQL.")
    if "descrizione" in lowered_sql and re.search(r"\b(?:like|ilike)\b", lowered_sql):
        return _semantic_description_query_guidance()

    forbidden_tokens = (
        " insert ",
        " update ",
        " delete ",
        " drop ",
        " alter ",
        " pragma ",
        " attach ",
        " detach ",
        " create ",
        " replace ",
    )
    padded_sql = f" {lowered_sql} "
    if any(token in padded_sql for token in forbidden_tokens):
        raise ValueError("La query contiene istruzioni non consentite.")

    try:
        with engine.connect() as connection:
            connection.execute(sql_text("DROP VIEW IF EXISTS temp.movimenti_bancari"))
            connection.execute(sql_text("DROP VIEW IF EXISTS temp.utente"))
            connection.execute(
                sql_text(
                    f"""
                    CREATE TEMP VIEW movimenti_bancari AS
                    SELECT id, user_id, data, descrizione, importo, note, categoria, macrocategoria
                    FROM main.movimenti_bancari
                    WHERE user_id = {int(current_user_id)}
                    """
                )
            )
            connection.execute(
                sql_text(
                    f"""
                    CREATE TEMP VIEW utente AS
                    SELECT
                        user_id,
                        stipendio_mensile,
                        spese_fisse_essenziali_mensili,
                        disponibile_mensile,
                        disponibile_settimanale,
                        obiettivo,
                        spese_irrinunciabili
                    FROM main.utente
                    WHERE user_id = {int(current_user_id)}
                    """
                )
            )
            result = connection.execute(sql_text(cleaned_sql))
            mappings = result.mappings().fetchmany(MAX_QUERY_ROWS + 1)
    except SQLAlchemyError as exc:
        return json.dumps(
            {
                "error": "Query SQL non valida per lo schema disponibile.",
                "details": str(exc),
                "tables": {
                    "movimenti_bancari": MOVIMENTI_BANCARI_COLUMNS,
                    "utente": UTENTE_COLUMNS,
                },
                "hint": "Per le richieste di analisi usa preferibilmente i tool dedicati per categoria, settimana, mese e storico.",
            },
            ensure_ascii=False,
            indent=2,
        )

    truncated = len(mappings) > MAX_QUERY_ROWS
    if truncated:
        mappings = mappings[:MAX_QUERY_ROWS]

    rows = [{key: value.isoformat() if isinstance(value, date) else value for key, value in row.items()} for row in mappings]
    return _rows_to_json(rows, truncated=truncated)


def mostra_schema_database() -> str:
    """Restituisce schema e informazioni operative per le tabelle principali del database."""
    return json.dumps(
        {
            "tables": {
                "movimenti_bancari": MOVIMENTI_BANCARI_COLUMNS,
                "utente": UTENTE_COLUMNS,
            },
            "table_schemas": TABLE_SCHEMAS,
            "classificazioni_movimenti": serialize_classification_schema(),
            "notes": [
                "Per analisi di categoria usa `analizza_spese_per_categoria`.",
                "Per analisi settimanali usa `analizza_spese_settimana`.",
                "Per analisi mensili usa `analizza_spese_mese`.",
                "Per domande semantiche tipo 'ho speso per pizza questo mese?' usa `ottieni_movimenti_mese_corrente`, non SQL LIKE su descrizione.",
                "Per storico completo usa `analizza_spese_complessive`.",
                "Per il calcolo delle spese fisse mensili da macrocategoria usa `calcola_spese_fisse_mensili`.",
                "Per insight guidati dall'obiettivo usa `genera_insight_settimanali` o `genera_insight_mensili`.",
                "I dati restituiti sono gia' limitati all'utente autenticato.",
                "I campi categoria e macrocategoria vengono valorizzati automaticamente in `aggiungi_movimenti`.",
                "Esiste un campo interno write-only di risparmio non esposto in lettura.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def mostra_schema_movimenti() -> str:
    """Compatibilita' retroattiva: restituisce lo schema del database principale."""
    return mostra_schema_database()


def analizza_spesa_categorie(payload: RichiestaAnalisiCategorieSpesa) -> str:
    """Compatibilita': delega al nuovo tool focalizzato sulle categorie."""
    return analizza_spese_per_categoria(
        RichiestaAnalisiPerCategoria(
            categorie=payload.categorie,
            periodo="totale",
            preview_limit=payload.preview_limit,
            soglia_importo_rilevante=payload.soglia_importo_mensile_rilevante,
        )
    )


ANALYSIS_TOOLS = [
    ottieni_profilo_utente,
    analizza_spese_per_categoria,
    analizza_spese_fisse,
    analizza_spese_settimana,
    analizza_spese_mese,
    analizza_spese_complessive,
    calcola_spese_fisse_mensili,
    genera_insight_settimanali,
    genera_insight_mensili,
    ottieni_movimenti_mese_corrente,
]

ROOT_TOOLS = [
    aggiungi_movimenti,
    cancella_movimenti,
    ottieni_profilo_utente,
    aggiorna_profilo_utente,
    aggiorna_risparmio_interno,
    stima_spese_fisse_essenziali,
    analizza_spese_per_categoria,
    analizza_spese_fisse,
    analizza_spese_settimana,
    analizza_spese_mese,
    analizza_spese_complessive,
    calcola_spese_fisse_mensili,
    genera_insight_settimanali,
    genera_insight_mensili,
    analizza_budget_attuale,
    analizza_spesa_categorie,
    ottieni_movimenti_mese_corrente,
    riepilogo_movimenti_database,
    costruisci_query_sql,
    esegui_query_sql,
    mostra_schema_database,
]
