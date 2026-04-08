from __future__ import annotations

from datetime import date
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from punkathon_agent.models.finance import CATEGORIA_TO_MACRO_CATEGORIA, CategoriaSpesa, MacroCategoriaSpesa
from punkathon_agent.punkagent.attachments import supported_attachment_formats
from punkathon_agent.punkagent.constants import SUPPORTED_ATTACHMENT_MIME_TYPES


class ApiAttachment(BaseModel):
    filename: str = Field(min_length=1, description="Nome file mostrato al modello")
    mime_type: str = Field(min_length=1, description="MIME type dell'allegato")
    base64_data: str = Field(min_length=1, description="Payload base64 puro, senza prefisso data:")

    @model_validator(mode="after")
    def validate_attachment(self) -> "ApiAttachment":
        if self.mime_type not in SUPPORTED_ATTACHMENT_MIME_TYPES:
            raise ValueError(f"Formato allegato non supportato. Supportati: {supported_attachment_formats()}")
        return self


class FrontendWeekBox(BaseModel):
    index: int = Field(ge=1, le=5)
    label: str = Field(min_length=1)
    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    total: float = Field(ge=0)
    contains_today: bool = False


class FrontendWeeklyOverview(BaseModel):
    month_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    month_label: str = Field(min_length=1)
    default_week_index: int | None = Field(default=None, ge=1, le=5)
    weeks: list[FrontendWeekBox] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_weeks(self) -> "FrontendWeeklyOverview":
        if len(self.weeks) > 5:
            raise ValueError("Il contesto settimanale frontend supporta al massimo 5 settimane visibili.")
        return self


class FrontendContext(BaseModel):
    weekly_overview: FrontendWeeklyOverview | None = None


class ChatRequest(BaseModel):
    message: str = Field(default="", description="Messaggio dell'utente")
    conversation: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Conversazione serializzata restituita dal turno precedente",
    )
    attachments: list[ApiAttachment] = Field(default_factory=list)
    frontend_context: FrontendContext | None = None

    @model_validator(mode="after")
    def validate_request(self) -> "ChatRequest":
        if not self.message.strip() and not self.attachments:
            raise ValueError("Specifica un messaggio oppure almeno un allegato.")
        return self


class ChatResponse(BaseModel):
    answer: str
    conversation: list[dict[str, Any]]


class GeneratedInsight(BaseModel):
    id: str = Field(min_length=1)
    type: Literal["success", "warning"]
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)


class InsightsResponse(BaseModel):
    generated_at: str = Field(min_length=1)
    window_start: str = Field(min_length=1)
    window_end: str = Field(min_length=1)
    insights: list[GeneratedInsight] = Field(default_factory=list)


class StatementFilters(BaseModel):
    selected_year: int = Field(ge=2000, le=2100)
    selected_month: int = Field(ge=1, le=12)
    selected_week: int = Field(ge=1, le=5)
    month_label: str = Field(min_length=1)
    period_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    available_years: list[int] = Field(default_factory=list)
    weeks: list[FrontendWeekBox] = Field(default_factory=list)


class StatementClassificationSchema(BaseModel):
    macrocategorie: list[str] = Field(default_factory=list)
    categorie: list[str] = Field(default_factory=list)
    mappa_categoria_macrocategoria: dict[str, str] = Field(default_factory=dict)


class StatementTransaction(BaseModel):
    id: str = Field(min_length=1)
    data: date
    descrizione: str = Field(min_length=1)
    note: str | None = None
    importo: float
    macrocategoria: str | None = None
    categoria: str | None = None


class StatementPageResponse(BaseModel):
    filters: StatementFilters
    classification_schema: StatementClassificationSchema
    transactions: list[StatementTransaction] = Field(default_factory=list)
    total_transactions: int = Field(ge=0)


class StatementTransactionWrite(BaseModel):
    data: date
    descrizione: str = Field(min_length=1)
    note: str | None = None
    importo: float
    macrocategoria: MacroCategoriaSpesa
    categoria: CategoriaSpesa

    @field_validator("descrizione", mode="before")
    @classmethod
    def normalize_descrizione(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("La descrizione e' obbligatoria.")
        return normalized

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_transaction(self) -> "StatementTransactionWrite":
        if round(float(self.importo), 2) == 0.0:
            raise ValueError("L'importo deve essere diverso da zero.")

        expected = CATEGORIA_TO_MACRO_CATEGORIA[self.categoria]
        if self.macrocategoria != expected:
            raise ValueError(
                f"La macrocategoria {self.macrocategoria.value!r} non e' valida per {self.categoria.value!r}."
            )

        return self


class StatementDeleteResponse(BaseModel):
    deleted: bool = True
    movement_id: str = Field(min_length=1)
