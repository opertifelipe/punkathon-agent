from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel

DEFAULT_USER_GOAL = "Controllo delle finanze"
EMAIL_MAX_LENGTH = 320
NAME_MAX_LENGTH = 120
PASSWORD_HASH_MAX_LENGTH = 256
MOVEMENT_DESCRIPTION_MAX_LENGTH = 512
CATEGORY_MAX_LENGTH = 128


class PunkUser(SQLModel, table=True):
    __tablename__ = "punk_users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(max_length=EMAIL_MAX_LENGTH, index=True, sa_column_kwargs={"unique": True})
    nome: str = Field(max_length=NAME_MAX_LENGTH)
    cognome: str = Field(max_length=NAME_MAX_LENGTH)
    eta: int
    password_hash: str = Field(max_length=PASSWORD_HASH_MAX_LENGTH)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MovimentoBancario(SQLModel, table=True):
    __tablename__ = "movimenti_bancari"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="punk_users.id", index=True)
    data: date = Field(index=True)
    descrizione: str = Field(max_length=MOVEMENT_DESCRIPTION_MAX_LENGTH, index=True)
    importo: float
    note: str | None = Field(default=None)
    categoria: str | None = Field(default=None, max_length=CATEGORY_MAX_LENGTH, index=True)
    macrocategoria: str | None = Field(default=None, max_length=CATEGORY_MAX_LENGTH, index=True)


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
