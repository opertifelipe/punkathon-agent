from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from jwt import ExpiredSignatureError, InvalidTokenError
from openai import AuthenticationError
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select
from sqlalchemy import func

from punkathon_agent.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    is_email_allowed,
    normalize_email,
    verify_password,
)
from punkathon_agent.db import get_session
from punkathon_agent.models.api import (
    ChatRequest,
    ChatResponse,
    FrontendWeekBox,
    GeneratedInsight,
    InsightsAvailabilityResponse,
    InsightsResponse,
    InsightSpeechRequest,
    SingleInsightRequest,
    StatementClassificationSchema,
    StatementBulkDeleteResponse,
    StatementDeleteResponse,
    StatementFilters,
    StatementPageResponse,
    StatementTransaction,
    StatementTransactionWrite,
)
from punkathon_agent.models.db import DEFAULT_USER_GOAL, MovimentoBancario, PunkUser, Utente
from punkathon_agent.models.finance import serialize_classification_schema
from punkathon_agent.punkagent import (
    get_punk_agent,
    run_agent_turn,
    run_agent_turn_streaming,
    serialize_conversation,
)
from punkathon_agent.services.statement_pdf_import import import_statement_pdf_attachments
from punkathon_agent.services.spending import _ensure_estimated_fixed_expenses, _sync_budget_fields
from punkathon_agent.services.ai_insights import (
    get_sidebar_insights_availability,
    generate_goal_based_sidebar_insights,
    generate_single_goal_based_insight,
)
from punkathon_agent.services.insight_tts import synthesize_insight_audio
from punkathon_agent.services.users import claim_legacy_data_for_first_user, ensure_user_profile


class AuthUserResponse(BaseModel):
    id: int
    email: str
    nome: str
    cognome: str
    eta: int


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class SignupRequest(BaseModel):
    email: str = Field(min_length=5)
    nome: str = Field(min_length=1)
    cognome: str = Field(min_length=1)
    eta: int = Field(ge=13, le=120)
    password: str = Field(min_length=8)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: Any) -> str:
        email = normalize_email(str(value or ""))
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Inserisci un'email valida.")
        return email

    @field_validator("nome", "cognome", mode="before")
    @classmethod
    def normalize_name_fields(cls, value: Any) -> str:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            raise ValueError("Campo obbligatorio.")
        return normalized

    @field_validator("password", mode="before")
    @classmethod
    def normalize_password(cls, value: Any) -> str:
        password = str(value or "")
        if len(password) < 8:
            raise ValueError("La password deve contenere almeno 8 caratteri.")
        return password


class SigninRequest(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_field(cls, value: Any) -> str:
        return normalize_email(str(value or ""))


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

bearer_scheme = HTTPBearer(auto_error=False)

app = FastAPI(
    title="Aurora API",
    version="0.1.0",
    description="API FastAPI per interrogare Aurora in modalita' classica o streaming.",
)


class ApiPrefixMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = str(scope.get("path", ""))
            if path == "/api":
                scope = {**scope, "path": "/"}
            elif path.startswith("/api/"):
                scope = {**scope, "path": path[4:]}

        await self.app(scope, receive, send)


AUTO_ATTACHMENT_IMPORT_PROMPT = (
    "Import automatico obbligatorio degli allegati di questa richiesta. "
    "Leggi tutti gli allegati, estrai tutti i movimenti bancari riconoscibili e salvali subito con `aggiungi_movimenti`. "
    "Subito dopo esegui `stima_spese_fisse_essenziali(sovrascrivi_valore_esistente=True)` per sincronizzare le spese fisse "
    "dal mese completo precedente e poi `calcola_spese_fisse_mensili`. "
    "Non chiedere conferma, non rimandare, non delegare gli allegati ai subagent. "
    "Se un allegato non contiene movimenti utili, dillo chiaramente. Rispondi con un riepilogo sintetico dell'esito."
)


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
app.add_middleware(ApiPrefixMiddleware)


def _inline_attachments_payload(attachments: list[Any]) -> list[dict[str, str]]:
    return [attachment.model_dump() for attachment in attachments]


def _build_visible_chat_message(message: str, *, attachments_were_processed: bool) -> str:
    if not attachments_were_processed:
        return message

    stripped_message = message.strip()
    user_request = stripped_message or (
        "Conferma brevemente l'esito dell'import automatico appena eseguito, "
        "indica che le spese fisse sono state ricalcolate se possibile e suggerisci cosa posso chiederti ora."
    )

    return (
        "Nota operativa: il tentativo di import automatico degli allegati di questa richiesta e' gia' stato eseguito "
        "prima di questo turno. Usa il database aggiornato risultante da quell'import e non chiedere di reinviare i file. "
        "Le spese fisse sono gia' state ricalcolate se i dati lo permettono.\n\n"
        f"Richiesta utente:\n{user_request}"
    )


def _run_automatic_attachment_import(
    *,
    attachments: list[dict[str, str]],
    user_id: int,
) -> tuple[str, bool]:
    return asyncio.run(
        _run_automatic_attachment_import_async(
            attachments=attachments,
            user_id=user_id,
        )
    )


def _run_agent_attachment_import(
    *,
    attachments: list[dict[str, str]],
    user_id: int,
) -> tuple[str, bool]:
    answer, _conversation, reload = run_agent_turn(
        get_punk_agent(),
        [],
        AUTO_ATTACHMENT_IMPORT_PROMPT,
        inline_attachments=attachments,
        user_id=user_id,
    )
    return answer, reload


async def _run_automatic_attachment_import_async(
    *,
    attachments: list[dict[str, str]],
    user_id: int,
) -> tuple[str, bool]:
    if not attachments:
        return "", False

    pdf_attachments = [attachment for attachment in attachments if attachment["mime_type"] == "application/pdf"]
    legacy_attachments = [attachment for attachment in attachments if attachment["mime_type"] != "application/pdf"]

    summaries: list[str] = []
    reload_required = False

    if pdf_attachments:
        pdf_summary, pdf_reload = await import_statement_pdf_attachments(
            pdf_attachments,
            user_id=user_id,
        )
        if pdf_summary:
            summaries.append(pdf_summary)
        reload_required = reload_required or pdf_reload

    if legacy_attachments:
        legacy_summary, legacy_reload = await asyncio.to_thread(
            _run_agent_attachment_import,
            attachments=legacy_attachments,
            user_id=user_id,
        )
        if legacy_summary:
            summaries.append(legacy_summary)
        reload_required = reload_required or legacy_reload

    return "\n\n".join(summary for summary in summaries if summary), reload_required


def _build_attachment_import_status_message(attachments: list[dict[str, str]]) -> str:
    has_pdf = any(attachment["mime_type"] == "application/pdf" for attachment in attachments)
    has_images = any(attachment["mime_type"].startswith("image/") for attachment in attachments)

    if has_pdf and has_images:
        return (
            "Import automatico allegati in corso. Sto dividendo i PDF in pagine, facendo OCR per pagina ed estraendo i movimenti dal testo in parallelo, "
            "salvando i movimenti nel database e gestendo le immagini con il flusso normale."
        )
    if has_pdf:
        return (
            "Import automatico PDF in corso. Sto dividendo l'estratto conto in pagine, facendo OCR per pagina ed estraendo i movimenti dal testo in parallelo "
            "e salvando subito i movimenti nel database."
        )
    return (
        "Import automatico allegati in corso. Sto salvando i movimenti nel database "
        "e ricalcolando subito le spese fisse."
    )


def _sse_event(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _serialize_user(user: PunkUser) -> AuthUserResponse:
    if user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        nome=user.nome,
        cognome=user.cognome,
        eta=user.eta,
    )


def _ensure_auth_email_allowed(email: str) -> None:
    if not is_email_allowed(email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accesso non abilitato per questa email.")


def _month_label(year: int, month: int) -> str:
    return f"{ITALIAN_MONTHS[month - 1]} {year}"


def _movement_statement_for_user(user_id: int) -> Any:
    return select(MovimentoBancario).where(MovimentoBancario.user_id == user_id)


def _movement_by_identity(
    session: Session,
    *,
    user_id: int,
    data: date,
    descrizione: str,
    importo: float,
    exclude_movement_id: int | None = None,
) -> MovimentoBancario | None:
    statement = (
        _movement_statement_for_user(user_id)
        .where(MovimentoBancario.data == data)
        .where(MovimentoBancario.descrizione == descrizione)
        .where(MovimentoBancario.importo == importo)
    )
    if exclude_movement_id is not None:
        statement = statement.where(MovimentoBancario.id != exclude_movement_id)
    return session.exec(statement).first()


def _ensure_user_profile(session: Session, user_id: int) -> Utente:
    return ensure_user_profile(session, user_id)


def _sync_profile_fixed_expenses(session: Session, utente: Utente, *, user_id: int) -> Utente:
    previous_budget = (utente.disponibile_mensile, utente.disponibile_settimanale)
    _, _, changed = _ensure_estimated_fixed_expenses(
        session,
        utente,
        overwrite_existing=True,
        user_id=user_id,
    )

    _sync_budget_fields(utente)
    budget_changed = previous_budget != (utente.disponibile_mensile, utente.disponibile_settimanale)

    if budget_changed:
        session.add(utente)
        session.commit()
        session.refresh(utente)
    elif changed:
        session.refresh(utente)

    return utente


def _claim_legacy_data_for_first_user(session: Session, user_id: int) -> None:
    claim_legacy_data_for_first_user(session, user_id)


def _expense_total_between(session: Session, *, user_id: int, start_date: date, end_date: date) -> float:
    statement = (
        select(func.sum(MovimentoBancario.importo))
        .where(MovimentoBancario.user_id == user_id)
        .where(MovimentoBancario.data >= start_date)
        .where(MovimentoBancario.data <= end_date)
        .where(MovimentoBancario.importo < 0)
    )
    total_raw = session.exec(statement).one()
    return round(abs(float(total_raw or 0.0)), 2)


def _build_week_boxes_from_start(
    session: Session,
    *,
    user_id: int,
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
                total=_expense_total_between(session, user_id=user_id, start_date=week_start, end_date=week_end),
                contains_today=week_start <= reference_day <= week_end,
            )
        )
    return weeks


def _available_statement_years(
    session: Session,
    *,
    user_id: int,
    selected_year: int,
    reference_day: date,
) -> list[int]:
    years = {selected_year, reference_day.year}
    for movement_date in session.exec(
        select(MovimentoBancario.data).where(MovimentoBancario.user_id == user_id)
    ).all():
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


def _serialize_movement_id(movement: MovimentoBancario) -> str:
    if movement.id is None:
        raise HTTPException(status_code=500, detail="Movimento senza identificatore persistito.")
    return str(movement.id)


def _deserialize_movement_id(movement_id: str) -> int:
    try:
        return int(movement_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Identificatore movimento non valido.") from exc


def _get_movement_or_404(session: Session, movement_id: str, *, user_id: int) -> MovimentoBancario:
    movement = session.get(MovimentoBancario, _deserialize_movement_id(movement_id))
    if movement is None or movement.user_id != user_id:
        raise HTTPException(status_code=404, detail="Movimento non trovato.")
    return movement


def _serialize_statement_transaction(movement: MovimentoBancario) -> StatementTransaction:
    return StatementTransaction(
        id=_serialize_movement_id(movement),
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
    user_id: int,
    start_date: date,
    end_date: date,
) -> list[StatementTransaction]:
    statement = (
        _movement_statement_for_user(user_id)
        .where(MovimentoBancario.data >= start_date)
        .where(MovimentoBancario.data <= end_date)
        .order_by(MovimentoBancario.data.desc(), MovimentoBancario.descrizione.asc(), MovimentoBancario.importo.asc())
    )
    return [_serialize_statement_transaction(item) for item in session.exec(statement).all()]


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db),
) -> PunkUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticazione richiesta.")

    try:
        user_id = decode_access_token(credentials.credentials)
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione scaduta.") from exc
    except (InvalidTokenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido.") from exc

    user = session.get(PunkUser, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato.")
    return user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/signup", response_model=AuthSessionResponse, status_code=201)
def signup(payload: SignupRequest, session: Session = Depends(get_db)) -> AuthSessionResponse:
    _ensure_auth_email_allowed(payload.email)

    existing = session.exec(select(PunkUser).where(PunkUser.email == payload.email)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Esiste gia' un account con questa email.")

    user = PunkUser(
        email=payload.email,
        nome=payload.nome,
        cognome=payload.cognome,
        eta=payload.eta,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    if user.id is None:
        raise HTTPException(status_code=500, detail="Impossibile creare il nuovo utente.")

    _claim_legacy_data_for_first_user(session, user.id)

    return AuthSessionResponse(
        access_token=create_access_token(user.id),
        user=_serialize_user(user),
    )


@app.post("/auth/signin", response_model=AuthSessionResponse)
def signin(payload: SigninRequest, session: Session = Depends(get_db)) -> AuthSessionResponse:
    _ensure_auth_email_allowed(payload.email)

    user = session.exec(select(PunkUser).where(PunkUser.email == payload.email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenziali non valide.")

    if user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    _ensure_user_profile(session, user.id)

    return AuthSessionResponse(
        access_token=create_access_token(user.id),
        user=_serialize_user(user),
    )


@app.get("/auth/me", response_model=AuthUserResponse)
def auth_me(current_user: PunkUser = Depends(get_current_user)) -> AuthUserResponse:
    return _serialize_user(current_user)


@app.post("/insights/generate", response_model=InsightsResponse)
def generate_insights(current_user: PunkUser = Depends(get_current_user)) -> InsightsResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    try:
        payload = generate_goal_based_sidebar_insights(user_id=current_user.id)
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


@app.get("/insights/status", response_model=InsightsAvailabilityResponse)
def insights_status(current_user: PunkUser = Depends(get_current_user)) -> InsightsAvailabilityResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    try:
        payload = get_sidebar_insights_availability(user_id=current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Impossibile verificare la disponibilita' degli insights: {exc}",
        ) from exc

    return InsightsAvailabilityResponse(**payload)


@app.post("/insights/generate-one", response_model=GeneratedInsight)
async def generate_single_insight(
    payload: SingleInsightRequest,
    current_user: PunkUser = Depends(get_current_user),
) -> GeneratedInsight:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    try:
        insight = await generate_single_goal_based_insight(
            insight_type=payload.type,
            focus_hint=payload.focus_hint,
            existing_titles=payload.existing_titles,
            user_id=current_user.id,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Impossibile generare l'insight AI: verifica la configurazione OpenAI.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Impossibile generare l'insight AI: {exc}",
        ) from exc

    return GeneratedInsight(**insight)


@app.post("/insights/text-to-speech")
def insight_text_to_speech(
    payload: InsightSpeechRequest,
    current_user: PunkUser = Depends(get_current_user),
) -> Response:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    try:
        audio_bytes = synthesize_insight_audio(payload.text)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Impossibile generare l'audio dell'insight: verifica la configurazione OpenAI.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Impossibile generare l'audio dell'insight: {exc}",
        ) from exc

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="insight.mp3"',
        },
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, current_user: PunkUser = Depends(get_current_user)) -> ChatResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    attachments_payload = _inline_attachments_payload(request.attachments)
    attachments_were_processed = bool(attachments_payload)
    _, preload_reload = _run_automatic_attachment_import(
        attachments=attachments_payload,
        user_id=current_user.id,
    )

    answer, conversation, turn_reload = run_agent_turn(
        get_punk_agent(),
        request.conversation,
        _build_visible_chat_message(
            request.message,
            attachments_were_processed=attachments_were_processed,
        ),
        inline_attachments=[] if attachments_were_processed else attachments_payload,
        frontend_context=request.frontend_context.model_dump(exclude_none=True) if request.frontend_context else None,
        user_id=current_user.id,
    )
    return ChatResponse(
        answer=answer,
        conversation=serialize_conversation(conversation),
        reload=preload_reload or turn_reload,
    )


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: PunkUser = Depends(get_current_user),
) -> StreamingResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def on_event(event: dict[str, str]) -> None:
        await queue.put(event)

    async def runner() -> None:
        try:
            attachments_payload = _inline_attachments_payload(request.attachments)
            attachments_were_processed = bool(attachments_payload)
            preload_reload = False

            if attachments_were_processed:
                await queue.put(
                    {
                        "type": "reasoning",
                        "content": _build_attachment_import_status_message(attachments_payload),
                    }
                )
                _import_answer, preload_reload = await _run_automatic_attachment_import_async(
                    attachments=attachments_payload,
                    user_id=current_user.id,
                )

            answer, conversation, turn_reload = await run_agent_turn_streaming(
                get_punk_agent(),
                request.conversation,
                _build_visible_chat_message(
                    request.message,
                    attachments_were_processed=attachments_were_processed,
                ),
                inline_attachments=[] if attachments_were_processed else attachments_payload,
                frontend_context=request.frontend_context.model_dump(exclude_none=True) if request.frontend_context else None,
                user_id=current_user.id,
                on_event=on_event,
            )
            await queue.put(
                {
                    "type": "done",
                    "answer": answer,
                    "conversation": serialize_conversation(conversation),
                    "reload": preload_reload or turn_reload,
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
def get_utente(
    session: Session = Depends(get_db),
    current_user: PunkUser = Depends(get_current_user),
) -> UtenteResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    utente = _sync_profile_fixed_expenses(
        session,
        _ensure_user_profile(session, current_user.id),
        user_id=current_user.id,
    )

    today = date.today()
    first_day = today.replace(day=1)
    stmt = (
        select(func.sum(MovimentoBancario.importo))
        .where(MovimentoBancario.user_id == current_user.id)
        .where(MovimentoBancario.data >= first_day)
        .where(MovimentoBancario.data <= today)
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
def patch_utente(
    payload: UtenteUpdate,
    session: Session = Depends(get_db),
    current_user: PunkUser = Depends(get_current_user),
) -> UtenteResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    utente = _ensure_user_profile(session, current_user.id)

    if payload.stipendio_mensile is not None:
        utente.stipendio_mensile = payload.stipendio_mensile
    if payload.obiettivo is not None:
        utente.obiettivo = payload.obiettivo.strip() or DEFAULT_USER_GOAL

    utente = _sync_profile_fixed_expenses(session, utente, user_id=current_user.id)

    return get_utente(session, current_user)


@app.get("/spese-settimanali", response_model=SpeseSettimanaliResponse)
def get_spese_settimanali(
    start_date: date | None = Query(default=None),
    session: Session = Depends(get_db),
    current_user: PunkUser = Depends(get_current_user),
) -> SpeseSettimanaliResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    reference_day = date.today()
    normalized_start = start_date or (reference_day - timedelta(days=28))
    weeks = _build_week_boxes_from_start(
        session,
        user_id=current_user.id,
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
    current_user: PunkUser = Depends(get_current_user),
) -> StatementPageResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    reference_day = date.today()
    selected_year = year or reference_day.year
    selected_month = month or reference_day.month
    month_start = _statement_month_start(selected_year, selected_month)
    weeks = _build_week_boxes_from_start(
        session,
        user_id=current_user.id,
        start_date=month_start,
        reference_day=reference_day,
    )
    selected_week = week or _default_statement_week(weeks)
    selected_window = weeks[selected_week - 1]
    transactions = _statement_transactions_between(
        session,
        user_id=current_user.id,
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
                user_id=current_user.id,
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
    current_user: PunkUser = Depends(get_current_user),
) -> StatementTransaction:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    existing = _movement_by_identity(
        session,
        user_id=current_user.id,
        data=payload.data,
        descrizione=payload.descrizione,
        importo=float(payload.importo),
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Esiste gia' un movimento con data, descrizione e importo identici.",
        )

    movement = MovimentoBancario(
        user_id=current_user.id,
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
    current_user: PunkUser = Depends(get_current_user),
) -> StatementTransaction:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    current = _get_movement_or_404(session, movement_id, user_id=current_user.id)
    duplicate = _movement_by_identity(
        session,
        user_id=current_user.id,
        data=payload.data,
        descrizione=payload.descrizione,
        importo=float(payload.importo),
        exclude_movement_id=current.id,
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail="Esiste gia' un movimento con data, descrizione e importo identici.",
        )

    current.data = payload.data
    current.descrizione = payload.descrizione
    current.importo = float(payload.importo)
    current.note = payload.note
    current.categoria = payload.categoria.value
    current.macrocategoria = payload.macrocategoria.value
    session.add(current)
    session.commit()
    session.refresh(current)

    return _serialize_statement_transaction(current)


@app.delete("/estratto-conto/movimenti/{movement_id}", response_model=StatementDeleteResponse)
def delete_statement_transaction(
    movement_id: str,
    session: Session = Depends(get_db),
    current_user: PunkUser = Depends(get_current_user),
) -> StatementDeleteResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    movement = _get_movement_or_404(session, movement_id, user_id=current_user.id)
    session.delete(movement)
    session.commit()

    return StatementDeleteResponse(movement_id=movement_id)


@app.delete("/estratto-conto/movimenti", response_model=StatementBulkDeleteResponse)
def delete_all_statement_transactions(
    session: Session = Depends(get_db),
    current_user: PunkUser = Depends(get_current_user),
) -> StatementBulkDeleteResponse:
    if current_user.id is None:
        raise HTTPException(status_code=500, detail="Utente senza identificatore persistito.")

    movements = session.exec(_movement_statement_for_user(current_user.id)).all()
    deleted_count = len(movements)

    for movement in movements:
        session.delete(movement)

    session.commit()

    return StatementBulkDeleteResponse(deleted=True, deleted_count=deleted_count)


def _mount_frontend_if_configured() -> None:
    raw_dist_path = os.getenv("PUNKAGENT_FRONTEND_DIST", "").strip()
    if not raw_dist_path:
        return

    dist_path = Path(raw_dist_path)
    if not (dist_path / "index.html").is_file():
        return

    app.mount("/", StaticFiles(directory=dist_path, html=True), name="frontend")


_mount_frontend_if_configured()


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
