from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
from contextlib import suppress
from datetime import date, timedelta
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AuthenticationError
from pydantic import BaseModel
from sqlalchemy import delete, func, update
from sqlmodel import Session, select

from punkathon_agent.db import get_session
from punkathon_agent.models.api import (
    ChatRequest,
    ChatResponse,
    FrontendWeekBox,
    InsightsResponse,
    StatementClassificationSchema,
    StatementDeleteResponse,
    StatementFilters,
    StatementPageResponse,
    StatementTransaction,
    StatementTransactionWrite,
)
from punkathon_agent.models.db import USER_PROFILE_ID, MovimentoBancario, Utente
from punkathon_agent.models.finance import serialize_classification_schema
from punkathon_agent.punkagent import (
    get_punk_agent,
    run_agent_turn,
    run_agent_turn_streaming,
    serialize_conversation,
)
from punkathon_agent.services.ai_insights import generate_goal_based_sidebar_insights

# ---------------------------------------------------------------------------
# Modelli REST aggiuntivi
# ---------------------------------------------------------------------------


class UtenteResponse(BaseModel):
    stipendio_mensile: float | None
    spese_fisse_essenziali_mensili: float | None
    disponibile_mensile: float | None
    obiettivo: str | None
    risparmio_mensile: float | None


class UtenteUpdate(BaseModel):
    stipendio_mensile: float | None = None
    obiettivo: str | None = None


class WeekData(BaseModel):
    start: str
    end: str
    total: float


class SpeseSettimanaliResponse(BaseModel):
    weeks: list[WeekData]


ITALIAN_MONTHS = [
    "Gennaio",
    "Febbraio",
    "Marzo",
    "Aprile",
    "Maggio",
    "Giugno",
    "Luglio",
    "Agosto",
    "Settembre",
    "Ottobre",
    "Novembre",
    "Dicembre",
]


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PunkAgent API",
    version="0.1.0",
    description="API FastAPI per interrogare PunkAgent in modalita' classica o streaming.",
)


# ---------------------------------------------------------------------------
# Dipendenza DB
# ---------------------------------------------------------------------------


def get_db() -> Any:
    session = get_session()
    try:
        yield session
    finally:
        session.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _inline_attachments_payload(attachments: list[Any]) -> list[dict[str, str]]:
    return [attachment.model_dump() for attachment in attachments]


def _sse_event(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _month_label(year: int, month: int) -> str:
    return f"{ITALIAN_MONTHS[month - 1]} {year}"


def _expense_total_between(session: Session, *, start_date: date, end_date: date) -> float:
    statement = select(func.sum(MovimentoBancario.importo)).where(
        MovimentoBancario.data >= start_date,
        MovimentoBancario.data <= end_date,
        MovimentoBancario.importo < 0,
    )
    total_raw = session.exec(statement).one()
    return round(abs(float(total_raw or 0.0)), 2)


def _build_week_boxes_from_start(
    session: Session,
    *,
    start_date: date,
    reference_day: date,
) -> list[FrontendWeekBox]:
    weeks: list[FrontendWeekBox] = []
    for index in range(1, 6):
        week_start = start_date + timedelta(days=(index - 1) * 7)
        week_end = week_start + timedelta(days=6)
        weeks.append(
            FrontendWeekBox(
                index=index,
                label=f"Settimana {index}",
                start=week_start.isoformat(),
                end=week_end.isoformat(),
                total=_expense_total_between(session, start_date=week_start, end_date=week_end),
                contains_today=week_start <= reference_day <= week_end,
            )
        )
    return weeks


def _available_statement_years(
    session: Session,
    *,
    selected_year: int,
    reference_day: date,
) -> list[int]:
    years = {selected_year, reference_day.year}
    for movement_date in session.exec(select(MovimentoBancario.data)).all():
        years.add(movement_date.year)

    first_year = min(years) - 1
    last_year = max(years) + 1
    return list(range(first_year, last_year + 1))


def _statement_month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _default_statement_week(weeks: list[FrontendWeekBox]) -> int:
    for week in weeks:
        if week.contains_today:
            return week.index
    return 1


def _serialize_movement_id(data: date, descrizione: str, importo: float) -> str:
    payload = json.dumps(
        [data.isoformat(), descrizione, repr(float(importo))],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _deserialize_movement_id(movement_id: str) -> tuple[date, str, float]:
    try:
        padding = "=" * (-len(movement_id) % 4)
        decoded = base64.urlsafe_b64decode(f"{movement_id}{padding}".encode("ascii")).decode("utf-8")
        data_raw, descrizione_raw, importo_raw = json.loads(decoded)
        return (date.fromisoformat(str(data_raw)), str(descrizione_raw), float(importo_raw))
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Identificatore movimento non valido.") from exc


def _get_movement_or_404(session: Session, movement_id: str) -> MovimentoBancario:
    movement = session.get(MovimentoBancario, _deserialize_movement_id(movement_id))
    if movement is None:
        raise HTTPException(status_code=404, detail="Movimento non trovato.")
    return movement


def _serialize_statement_transaction(movement: MovimentoBancario) -> StatementTransaction:
    return StatementTransaction(
        id=_serialize_movement_id(movement.data, movement.descrizione, movement.importo),
        data=movement.data,
        descrizione=movement.descrizione,
        note=movement.note,
        importo=round(float(movement.importo), 2),
        macrocategoria=movement.macrocategoria,
        categoria=movement.categoria,
    )


def _statement_transactions_between(
    session: Session,
    *,
    start_date: date,
    end_date: date,
) -> list[StatementTransaction]:
    statement = (
        select(MovimentoBancario)
        .where(MovimentoBancario.data >= start_date)
        .where(MovimentoBancario.data <= end_date)
        .order_by(MovimentoBancario.data.desc(), MovimentoBancario.descrizione.asc(), MovimentoBancario.importo.asc())
    )
    return [_serialize_statement_transaction(item) for item in session.exec(statement).all()]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/insights/generate", response_model=InsightsResponse)
def generate_insights() -> InsightsResponse:
    try:
        payload = generate_goal_based_sidebar_insights()
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Impossibile generare gli insights AI: verifica la configurazione OpenAI.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Impossibile generare gli insights AI: {exc}",
        ) from exc

    return InsightsResponse(**payload)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    answer, conversation = run_agent_turn(
        get_punk_agent(),
        request.conversation,
        request.message,
        inline_attachments=_inline_attachments_payload(request.attachments),
        frontend_context=request.frontend_context.model_dump(exclude_none=True) if request.frontend_context else None,
    )
    return ChatResponse(
        answer=answer,
        conversation=serialize_conversation(conversation),
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def on_event(event: dict[str, str]) -> None:
        await queue.put(event)

    async def runner() -> None:
        try:
            answer, conversation = await run_agent_turn_streaming(
                get_punk_agent(),
                request.conversation,
                request.message,
                inline_attachments=_inline_attachments_payload(request.attachments),
                frontend_context=request.frontend_context.model_dump(exclude_none=True) if request.frontend_context else None,
                on_event=on_event,
            )
            await queue.put(
                {
                    "type": "done",
                    "answer": answer,
                    "conversation": serialize_conversation(conversation),
                }
            )
        except Exception as exc:
            await queue.put({"type": "error", "content": str(exc)})
        finally:
            await queue.put({"type": "close"})

    async def event_stream() -> Any:
        task = asyncio.create_task(runner())

        try:
            while True:
                event = await queue.get()
                event_type = event.get("type", "message")
                if event_type == "close":
                    break
                yield _sse_event(event_type, event)
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/utente", response_model=UtenteResponse)
def get_utente(session: Session = Depends(get_db)) -> UtenteResponse:
    utente = session.get(Utente, USER_PROFILE_ID)
    if utente is None:
        raise HTTPException(status_code=404, detail="Profilo utente non trovato")

    today = date.today()
    first_day = today.replace(day=1)
    stmt = select(func.sum(MovimentoBancario.importo)).where(
        MovimentoBancario.data >= first_day,
        MovimentoBancario.data <= today,
    )
    risparmio_raw = session.exec(stmt).one()
    risparmio_mensile = round(risparmio_raw or 0.0, 2)

    return UtenteResponse(
        stipendio_mensile=utente.stipendio_mensile,
        spese_fisse_essenziali_mensili=utente.spese_fisse_essenziali_mensili,
        disponibile_mensile=utente.disponibile_mensile,
        obiettivo=utente.obiettivo,
        risparmio_mensile=risparmio_mensile,
    )


@app.patch("/utente", response_model=UtenteResponse)
def patch_utente(payload: UtenteUpdate, session: Session = Depends(get_db)) -> UtenteResponse:
    utente = session.get(Utente, USER_PROFILE_ID)
    if utente is None:
        utente = Utente(id=USER_PROFILE_ID)

    if payload.stipendio_mensile is not None:
        utente.stipendio_mensile = payload.stipendio_mensile
    if payload.obiettivo is not None:
        utente.obiettivo = payload.obiettivo

    if utente.stipendio_mensile is not None and utente.spese_fisse_essenziali_mensili is not None:
        utente.disponibile_mensile = utente.stipendio_mensile - utente.spese_fisse_essenziali_mensili
        utente.disponibile_settimanale = utente.disponibile_mensile / 4

    session.add(utente)
    session.commit()
    session.refresh(utente)

    return get_utente(session)


@app.get("/spese-settimanali", response_model=SpeseSettimanaliResponse)
def get_spese_settimanali(
    start_date: date | None = Query(default=None),
    session: Session = Depends(get_db),
) -> SpeseSettimanaliResponse:
    reference_day = date.today()
    normalized_start = start_date or (reference_day - timedelta(days=28))
    weeks = _build_week_boxes_from_start(
        session,
        start_date=normalized_start,
        reference_day=reference_day,
    )

    return SpeseSettimanaliResponse(
        weeks=[WeekData(start=week.start, end=week.end, total=week.total) for week in weeks]
    )


@app.get("/estratto-conto", response_model=StatementPageResponse)
def get_statement_page(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    week: int | None = Query(default=None, ge=1, le=5),
    session: Session = Depends(get_db),
) -> StatementPageResponse:
    reference_day = date.today()
    selected_year = year or reference_day.year
    selected_month = month or reference_day.month
    month_start = _statement_month_start(selected_year, selected_month)
    weeks = _build_week_boxes_from_start(session, start_date=month_start, reference_day=reference_day)
    selected_week = week or _default_statement_week(weeks)
    selected_window = weeks[selected_week - 1]
    transactions = _statement_transactions_between(
        session,
        start_date=date.fromisoformat(selected_window.start),
        end_date=date.fromisoformat(selected_window.end),
    )

    return StatementPageResponse(
        filters=StatementFilters(
            selected_year=selected_year,
            selected_month=selected_month,
            selected_week=selected_week,
            month_label=_month_label(selected_year, selected_month),
            period_start=selected_window.start,
            period_end=selected_window.end,
            available_years=_available_statement_years(
                session,
                selected_year=selected_year,
                reference_day=reference_day,
            ),
            weeks=weeks,
        ),
        classification_schema=StatementClassificationSchema(**serialize_classification_schema()),
        transactions=transactions,
        total_transactions=len(transactions),
    )


@app.post("/estratto-conto/movimenti", response_model=StatementTransaction, status_code=201)
def create_statement_transaction(
    payload: StatementTransactionWrite,
    session: Session = Depends(get_db),
) -> StatementTransaction:
    primary_key = (payload.data, payload.descrizione, float(payload.importo))
    if session.get(MovimentoBancario, primary_key) is not None:
        raise HTTPException(
            status_code=409,
            detail="Esiste gia' un movimento con data, descrizione e importo identici.",
        )

    movement = MovimentoBancario(
        data=payload.data,
        descrizione=payload.descrizione,
        importo=float(payload.importo),
        note=payload.note,
        categoria=payload.categoria.value,
        macrocategoria=payload.macrocategoria.value,
    )
    session.add(movement)
    session.commit()
    session.refresh(movement)
    return _serialize_statement_transaction(movement)


@app.put("/estratto-conto/movimenti/{movement_id}", response_model=StatementTransaction)
def update_statement_transaction(
    movement_id: str,
    payload: StatementTransactionWrite,
    session: Session = Depends(get_db),
) -> StatementTransaction:
    current = _get_movement_or_404(session, movement_id)
    current_key = (current.data, current.descrizione, float(current.importo))
    next_key = (payload.data, payload.descrizione, float(payload.importo))

    if next_key != current_key and session.get(MovimentoBancario, next_key) is not None:
        raise HTTPException(
            status_code=409,
            detail="Esiste gia' un movimento con data, descrizione e importo identici.",
        )

    session.exec(
        update(MovimentoBancario)
        .where(MovimentoBancario.data == current_key[0])
        .where(MovimentoBancario.descrizione == current_key[1])
        .where(MovimentoBancario.importo == current_key[2])
        .values(
            data=payload.data,
            descrizione=payload.descrizione,
            importo=float(payload.importo),
            note=payload.note,
            categoria=payload.categoria.value,
            macrocategoria=payload.macrocategoria.value,
        )
    )
    session.commit()

    updated = session.get(MovimentoBancario, next_key)
    if updated is None:
        raise HTTPException(status_code=500, detail="Impossibile ricaricare il movimento aggiornato.")
    return _serialize_statement_transaction(updated)


@app.delete("/estratto-conto/movimenti/{movement_id}", response_model=StatementDeleteResponse)
def delete_statement_transaction(
    movement_id: str,
    session: Session = Depends(get_db),
) -> StatementDeleteResponse:
    movement = _get_movement_or_404(session, movement_id)
    session.exec(
        delete(MovimentoBancario)
        .where(MovimentoBancario.data == movement.data)
        .where(MovimentoBancario.descrizione == movement.descrizione)
        .where(MovimentoBancario.importo == movement.importo)
    )
    session.commit()

    return StatementDeleteResponse(movement_id=movement_id)


def main() -> None:
    host = os.getenv("PUNKAGENT_API_HOST") or os.getenv("PUNKATHON_API_HOST", "127.0.0.1")
    port = int(os.getenv("PUNKAGENT_API_PORT") or os.getenv("PUNKATHON_API_PORT", "8000"))
    uvicorn.run(
        "punkathon_agent.cli.api:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
