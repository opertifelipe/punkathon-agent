from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from punkathon_agent.db import create_database, get_session
from punkathon_agent.models.db import Utente
from punkathon_agent.punkagent.runtime import build_chat_model
from punkathon_agent.services.spending import (
    _build_period_summary,
    _build_recurring_item_breakdown,
    _fetch_all_movements,
    _fetch_movements_between,
    _get_or_create_user_profile,
    _round_money,
    _serialize_profile,
    _sync_budget_fields,
    build_fixed_expense_monthly_summary,
)


class SidebarInsightDraft(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class SidebarInsightsLLMOutput(BaseModel):
    positive_insights: list[SidebarInsightDraft] = Field(default_factory=list)
    attention_points: list[SidebarInsightDraft] = Field(default_factory=list)


_SIDEBAR_INSIGHTS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Sei un analista di finanza personale.

Devi generare insight brevi, chiari e concreti in italiano, usando solo i dati forniti.

Vincoli obbligatori:
- restituisci al massimo 3 `positive_insights`
- restituisci al massimo 3 `attention_points`
- ogni titolo deve essere breve e specifico
- ogni descrizione deve essere pratica, legata ai numeri o ai pattern osservati
- non inventare dati, percentuali o trend non presenti nel contesto
- se i dati sono deboli, restituisci meno insight invece di riempire con frasi generiche
- se manca l'obiettivo utente, almeno un punto di attenzione deve segnalarlo chiaramente
- gli insight positivi devono evidenziare segnali utili verso l'obiettivo o comportamenti virtuosi
- i punti di attenzione devono segnalare rischi, derive di spesa o aree da monitorare
"""
        ),
        (
            "human",
            """Analizza il seguente contesto sugli ultimi 3 mesi e genera insight per la sidebar.

Contesto JSON:
{context_json}
""",
        ),
    ]
)


def _month_start_months_ago(reference_date: date, months_ago: int) -> date:
    year = reference_date.year
    month = reference_date.month - months_ago

    while month <= 0:
        year -= 1
        month += 12

    return date(year, month, 1)


def _month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def _last_three_month_window(reference_date: date | None = None) -> dict[str, Any]:
    end_date = reference_date or date.today()
    start_date = _month_start_months_ago(end_date, 2)

    month_windows: list[dict[str, Any]] = []
    for months_ago in (2, 1, 0):
        month_start = _month_start_months_ago(end_date, months_ago)
        month_windows.append(
            {
                "label": month_start.strftime("%Y-%m"),
                "start_date": month_start,
                "end_date": end_date if months_ago == 0 else _month_end(month_start),
                "is_current": months_ago == 0,
            }
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "month_windows": month_windows,
    }


def _build_recent_context(
    *,
    profile: Utente,
    recent_movements: list[Any],
    all_movements: list[Any],
    analysis_window: dict[str, Any],
) -> dict[str, Any]:
    combined_summary = _build_period_summary(
        recent_movements,
        start_date=analysis_window["start_date"],
        end_date=analysis_window["end_date"],
        label="ultimi_3_mesi",
        period_type="ultimi_3_mesi",
        is_current=True,
        preview_limit=5,
    )

    monthly_breakdown: list[dict[str, Any]] = []
    for month_window in analysis_window["month_windows"]:
        month_movements = [
            movement
            for movement in recent_movements
            if month_window["start_date"] <= movement.data <= month_window["end_date"]
        ]
        summary = _build_period_summary(
            month_movements,
            start_date=month_window["start_date"],
            end_date=month_window["end_date"],
            label=month_window["label"],
            period_type="mese",
            is_current=month_window["is_current"],
            preview_limit=3,
        )
        monthly_breakdown.append(
            {
                "mese": month_window["label"],
                "da": month_window["start_date"].isoformat(),
                "a": month_window["end_date"].isoformat(),
                "spese": summary["totali"]["spese"],
                "entrate": summary["totali"]["entrate"],
                "saldo": summary["totali"]["saldo"],
                "top_categorie": summary["spese_per_categoria"][:3],
            }
        )

    recurring_items = _build_recurring_item_breakdown(
        recent_movements,
        threshold=75.0,
        preview_limit=5,
    )
    fixed_summary = build_fixed_expense_monthly_summary(
        all_movements,
        reference_date=analysis_window["end_date"],
        preview_limit=5,
    )

    return {
        "finestra_analisi": {
            "da": analysis_window["start_date"].isoformat(),
            "a": analysis_window["end_date"].isoformat(),
            "mesi": [month_window["label"] for month_window in analysis_window["month_windows"]],
        },
        "profilo_utente": _serialize_profile(profile),
        "spesa_irrinunciabili": profile.spese_irrinunciabili,
        "totali_ultimi_3_mesi": combined_summary["totali"],
        "spese_per_categoria": combined_summary["spese_per_categoria"][:6],
        "spese_per_macrocategoria": combined_summary["spese_per_macrocategoria"][:4],
        "top_spese_recenti": combined_summary["top_spese"][:5],
        "movimenti_ultimi_3_mesi": {
            "conteggio_movimenti": combined_summary["conteggio_movimenti"],
            "conteggio_spese": combined_summary["conteggio_spese"],
            "conteggio_entrate": combined_summary["conteggio_entrate"],
        },
        "andamento_mensile": monthly_breakdown,
        "voci_ricorrenti_da_rivedere": recurring_items,
        "spese_fisse": {
            "spese_fisse_essenziali_mensili": _round_money(profile.spese_fisse_essenziali_mensili),
            "spese_fisse_da_macrocategoria": fixed_summary,
        },
    }


def _invoke_sidebar_insights_model(context: dict[str, Any]) -> SidebarInsightsLLMOutput:
    structured_model = build_chat_model().with_structured_output(SidebarInsightsLLMOutput)
    chain = _SIDEBAR_INSIGHTS_PROMPT | structured_model
    return chain.invoke({"context_json": json.dumps(context, ensure_ascii=False, indent=2)})


def _clean_text(value: str, *, max_length: int) -> str:
    cleaned = " ".join(value.split()).strip(" -")
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip() + "..."


def _normalize_generated_insights(
    payload: SidebarInsightsLLMOutput,
    *,
    generated_at: datetime,
) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for insight_type, rows in (
        ("success", payload.positive_insights[:3]),
        ("warning", payload.attention_points[:3]),
    ):
        for row in rows:
            title = _clean_text(row.title, max_length=72)
            description = _clean_text(row.description, max_length=220)
            if not title or not description:
                continue

            fingerprint = (title.casefold(), description.casefold())
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            insights.append(
                {
                    "id": uuid4().hex,
                    "type": insight_type,
                    "title": title,
                    "description": description,
                    "timestamp": generated_at.isoformat(),
                }
            )

    if insights:
        return insights

    return [
        {
            "id": uuid4().hex,
            "type": "warning",
            "title": "Contesto troppo debole",
            "description": "Non ho trovato abbastanza segnali solidi negli ultimi 3 mesi per produrre insight affidabili.",
            "timestamp": generated_at.isoformat(),
        }
    ]


def generate_goal_based_sidebar_insights(
    reference_date: date | None = None,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    create_database()
    analysis_window = _last_three_month_window(reference_date)

    with get_session() as session:
        profile = _get_or_create_user_profile(session, user_id=user_id)
        _sync_budget_fields(profile)
        all_movements = _fetch_all_movements(session, user_id=user_id)
        recent_movements = _fetch_movements_between(
            session,
            start_date=analysis_window["start_date"],
            end_date=analysis_window["end_date"],
            user_id=user_id,
        )

    context = _build_recent_context(
        profile=profile,
        recent_movements=recent_movements,
        all_movements=all_movements,
        analysis_window=analysis_window,
    )
    llm_output = _invoke_sidebar_insights_model(context)
    generated_at = datetime.now(timezone.utc)

    return {
        "generated_at": generated_at.isoformat(),
        "window_start": analysis_window["start_date"].isoformat(),
        "window_end": analysis_window["end_date"].isoformat(),
        "insights": _normalize_generated_insights(llm_output, generated_at=generated_at),
    }


__all__ = [
    "SidebarInsightDraft",
    "SidebarInsightsLLMOutput",
    "_last_three_month_window",
    "_normalize_generated_insights",
    "generate_goal_based_sidebar_insights",
]
