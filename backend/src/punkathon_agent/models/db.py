from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel

DEFAULT_USER_GOAL = "Controllare le spese"


class PunkUser(SQLModel, table=True):
    __tablename__ = "punk_users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, sa_column_kwargs={"unique": True})
    nome: str
    cognome: str
    eta: int
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MovimentoBancario(SQLModel, table=True):
    __tablename__ = "movimenti_bancari"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="punk_users.id", index=True)
    data: date = Field(index=True)
    descrizione: str = Field(index=True)
    importo: float
    note: str | None = Field(default=None)
    categoria: str | None = Field(default=None, index=True)
    macrocategoria: str | None = Field(default=None, index=True)


class Utente(SQLModel, table=True):
    __tablename__ = "utente"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="punk_users.id", index=True, sa_column_kwargs={"unique": True})
    stipendio_mensile: float | None = Field(default=None)
    spese_fisse_essenziali_mensili: float | None = Field(default=None)
    disponibile_mensile: float | None = Field(default=None)
    disponibile_settimanale: float | None = Field(default=None)
    obiettivo: str | None = Field(default=DEFAULT_USER_GOAL)
    spese_irrinunciabili: str | None = Field(default=None)
    risparmio: float | None = Field(default=None)
