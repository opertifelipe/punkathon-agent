from __future__ import annotations

from datetime import date

from sqlmodel import Field, SQLModel

USER_PROFILE_ID = 1


class MovimentoBancario(SQLModel, table=True):
    __tablename__ = "movimenti_bancari"

    data: date = Field(primary_key=True, index=True)
    descrizione: str = Field(primary_key=True, index=True)
    importo: float = Field(primary_key=True)
    note: str | None = Field(default=None)
    categoria: str | None = Field(default=None, index=True)
    macrocategoria: str | None = Field(default=None, index=True)


class Utente(SQLModel, table=True):
    __tablename__ = "utente"

    id: int = Field(default=USER_PROFILE_ID, primary_key=True)
    stipendio_mensile: float | None = Field(default=None)
    spese_fisse_essenziali_mensili: float | None = Field(default=None)
    disponibile_mensile: float | None = Field(default=None)
    disponibile_settimanale: float | None = Field(default=None)
    obiettivo: str | None = Field(default=None)
    spese_irrinunciabili: str | None = Field(default=None)
    risparmio: float | None = Field(default=None)
