from __future__ import annotations

from datetime import date
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field, model_validator

from .finance import CategoriaSpesa

MessageContent: TypeAlias = str | list[dict[str, Any]]
SQLScalarValue: TypeAlias = str | float | int | date
PeriodoAnalisi: TypeAlias = Literal["settimana", "mese", "totale"]


class MovimentoInput(BaseModel):
    data: date = Field(description="Data del movimento in formato YYYY-MM-DD")
    descrizione: str = Field(description="Descrizione del movimento")
    importo: float = Field(description="Importo del movimento")
    note: str | None = Field(default=None, description="Note opzionali")


class FiltroCancellazione(BaseModel):
    data: date | None = Field(default=None, description="Cancella solo i movimenti di questa data")
    data_da: date | None = Field(default=None, description="Data iniziale inclusa")
    data_a: date | None = Field(default=None, description="Data finale inclusa")
    descrizione_contiene: str | None = Field(default=None, description="Sottostringa contenuta nella descrizione")
    importo_min: float | None = Field(default=None, description="Importo minimo incluso")
    importo_max: float | None = Field(default=None, description="Importo massimo incluso")
    note_contiene: str | None = Field(default=None, description="Sottostringa contenuta nelle note")

    @model_validator(mode="after")
    def validate_filters(self) -> "FiltroCancellazione":
        has_filter = any(
            value is not None
            for value in (
                self.data,
                self.data_da,
                self.data_a,
                self.descrizione_contiene,
                self.importo_min,
                self.importo_max,
                self.note_contiene,
            )
        )
        if not has_filter:
            raise ValueError("Specifica almeno un filtro per cancellare movimenti.")
        return self


class ProfiloUtenteUpdate(BaseModel):
    stipendio_mensile: float | None = Field(default=None, ge=0, description="Stipendio mensile netto dell'utente")
    spese_fisse_essenziali_mensili: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Totale mensile delle spese fisse essenziali del profilo; "
            "usa questo campo anche quando l'utente chiede in chat di modificare il valore delle spese"
        ),
    )
    obiettivo: str | None = Field(default=None, description="Obiettivo finanziario espresso in linguaggio naturale")
    spese_irrinunciabili: str | None = Field(
        default=None,
        description="Descrizione sintetica delle spese che l'utente considera irrinunciabili",
    )

    @model_validator(mode="after")
    def validate_payload(self) -> "ProfiloUtenteUpdate":
        if (
            self.stipendio_mensile is None
            and self.spese_fisse_essenziali_mensili is None
            and self.obiettivo is None
            and self.spese_irrinunciabili is None
        ):
            raise ValueError("Specifica almeno un valore da aggiornare nel profilo utente.")
        return self


class RisparmioInternoUpdate(BaseModel):
    risparmio: float | None = Field(default=None, ge=0, description="Valore interno del risparmio")
    motivo: str = Field(description="Motivo tecnico sintetico dell'aggiornamento interno")


class FiltroQuerySQL(BaseModel):
    colonna: str = Field(description="Nome della colonna su cui applicare il filtro")
    operatore: Literal[
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "contains",
        "starts_with",
        "ends_with",
        "in",
        "not_in",
        "between",
        "is_null",
        "is_not_null",
    ] = Field(description="Operatore SQL logico da usare nel WHERE")
    valore: SQLScalarValue | list[SQLScalarValue] | None = Field(
        default=None,
        description="Valore principale del filtro; per `in`/`not_in` usa una lista",
    )
    secondo_valore: SQLScalarValue | None = Field(
        default=None,
        description="Secondo valore solo per l'operatore `between`",
    )
    combina_con_precedente: Literal["and", "or"] = Field(
        default="and",
        description="Come combinare questo filtro con il precedente",
    )


class AggregazioneQuerySQL(BaseModel):
    funzione: Literal["count", "sum", "avg", "min", "max"] = Field(
        description="Funzione di aggregazione SQL da applicare"
    )
    colonna: str = Field(
        description="Nome della colonna da aggregare; usa `*` solo con `count` per contare le righe"
    )
    alias: str | None = Field(default=None, description="Alias opzionale della colonna aggregata")


class OrdinamentoQuerySQL(BaseModel):
    campo: str = Field(description="Colonna o alias per l'ordinamento finale")
    direzione: Literal["asc", "desc"] = Field(default="asc", description="Direzione ordinamento")


class RichiestaCostruzioneQuerySQL(BaseModel):
    tabella: Literal["movimenti_bancari", "utente"] = Field(description="Tabella target della SELECT")
    colonne: list[str] = Field(
        default_factory=list,
        description="Colonne da selezionare esplicitamente; se vuoto senza aggregazioni usa tutte le colonne leggibili",
    )
    filtri: list[FiltroQuerySQL] = Field(default_factory=list, description="Filtri del WHERE in ordine")
    aggregazioni: list[AggregazioneQuerySQL] = Field(
        default_factory=list,
        description="Aggregazioni opzionali da includere nella SELECT",
    )
    group_by: list[str] = Field(default_factory=list, description="Colonne del GROUP BY")
    order_by: list[OrdinamentoQuerySQL] = Field(default_factory=list, description="Ordinamenti finali")
    limit: int | None = Field(default=None, ge=1, le=200, description="LIMIT opzionale della query")
    distinct: bool = Field(default=False, description="Se true aggiunge DISTINCT alla SELECT")

    @model_validator(mode="after")
    def validate_request(self) -> "RichiestaCostruzioneQuerySQL":
        if self.distinct and self.aggregazioni:
            raise ValueError("`distinct` con aggregazioni non e' supportato in questo builder.")
        return self


class RichiestaAnalisiCategorieSpesa(BaseModel):
    categorie: list[CategoriaSpesa] = Field(description="Categorie esplicite da analizzare")
    preview_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Numero massimo di voci o movimenti da includere nei riepiloghi",
    )
    soglia_importo_mensile_rilevante: float = Field(
        default=10,
        ge=0,
        description="Soglia oltre la quale una voce ricorrente viene considerata rilevante",
    )

    @model_validator(mode="after")
    def validate_categories(self) -> "RichiestaAnalisiCategorieSpesa":
        if not self.categorie:
            raise ValueError("Specifica almeno una categoria da analizzare.")
        return self


class RichiestaAnalisiPerCategoria(BaseModel):
    categorie: list[CategoriaSpesa] = Field(description="Categorie esplicite da analizzare")
    periodo: PeriodoAnalisi = Field(
        default="totale",
        description="Periodo da analizzare: `settimana`, `mese` oppure `totale`",
    )
    settimana_iso: str | None = Field(
        default=None,
        pattern=r"^\d{4}-W\d{2}$",
        description="Settimana ISO facoltativa nel formato YYYY-Www; se assente usa la settimana corrente",
    )
    data_da: date | None = Field(
        default=None,
        description="Data iniziale inclusa di una finestra settimanale custom dal frontend",
    )
    data_a: date | None = Field(
        default=None,
        description="Data finale inclusa di una finestra settimanale custom dal frontend",
    )
    label_periodo: str | None = Field(
        default=None,
        description="Etichetta opzionale della finestra custom, per esempio `Settimana 3`",
    )
    mese: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}$",
        description="Mese facoltativo nel formato YYYY-MM; se assente usa il mese corrente",
    )
    preview_limit: int = Field(default=5, ge=1, le=20, description="Numero massimo di movimenti da mostrare")
    soglia_importo_rilevante: float = Field(
        default=10,
        ge=0,
        description="Soglia usata per evidenziare voci ricorrenti o rilevanti",
    )

    @model_validator(mode="after")
    def validate_request(self) -> "RichiestaAnalisiPerCategoria":
        if not self.categorie:
            raise ValueError("Specifica almeno una categoria da analizzare.")
        if self.periodo != "settimana" and self.settimana_iso is not None:
            raise ValueError("`settimana_iso` e' ammesso solo con periodo `settimana`.")
        if self.periodo != "settimana" and any(value is not None for value in (self.data_da, self.data_a, self.label_periodo)):
            raise ValueError("`data_da`, `data_a` e `label_periodo` sono ammessi solo con periodo `settimana`.")
        if self.periodo != "mese" and self.mese is not None:
            raise ValueError("`mese` e' ammesso solo con periodo `mese`.")
        if (self.data_da is None) != (self.data_a is None):
            raise ValueError("Per una settimana custom devi specificare sia `data_da` sia `data_a`.")
        if self.settimana_iso is not None and self.data_da is not None:
            raise ValueError("Non puoi combinare `settimana_iso` con una finestra custom `data_da`/`data_a`.")
        return self


class RichiestaAnalisiSettimana(BaseModel):
    settimana_iso: str | None = Field(
        default=None,
        pattern=r"^\d{4}-W\d{2}$",
        description="Settimana ISO nel formato YYYY-Www; se assente usa la settimana corrente",
    )
    data_da: date | None = Field(
        default=None,
        description="Data iniziale inclusa di una finestra settimanale custom dal frontend",
    )
    data_a: date | None = Field(
        default=None,
        description="Data finale inclusa di una finestra settimanale custom dal frontend",
    )
    label_periodo: str | None = Field(
        default=None,
        description="Etichetta opzionale della finestra custom, per esempio `Settimana 2`",
    )
    preview_limit: int = Field(default=5, ge=1, le=20, description="Numero massimo di movimenti da mostrare")

    @model_validator(mode="after")
    def validate_request(self) -> "RichiestaAnalisiSettimana":
        if (self.data_da is None) != (self.data_a is None):
            raise ValueError("Per una settimana custom devi specificare sia `data_da` sia `data_a`.")
        if self.settimana_iso is not None and self.data_da is not None:
            raise ValueError("Non puoi combinare `settimana_iso` con una finestra custom `data_da`/`data_a`.")
        return self


class RichiestaAnalisiMese(BaseModel):
    mese: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}$",
        description="Mese nel formato YYYY-MM; se assente usa il mese corrente",
    )
    preview_limit: int = Field(default=5, ge=1, le=20, description="Numero massimo di movimenti da mostrare")


class RichiestaAnalisiStorica(BaseModel):
    preview_limit: int = Field(default=5, ge=1, le=20, description="Numero massimo di movimenti da mostrare")


class RichiestaInsightObiettivo(BaseModel):
    periodo: Literal["settimana", "mese"] = Field(description="Periodo dell'insight")
    settimana_iso: str | None = Field(
        default=None,
        pattern=r"^\d{4}-W\d{2}$",
        description="Settimana ISO nel formato YYYY-Www; se assente usa la settimana corrente",
    )
    data_da: date | None = Field(
        default=None,
        description="Data iniziale inclusa di una finestra settimanale custom dal frontend",
    )
    data_a: date | None = Field(
        default=None,
        description="Data finale inclusa di una finestra settimanale custom dal frontend",
    )
    label_periodo: str | None = Field(
        default=None,
        description="Etichetta opzionale della finestra custom, per esempio `Settimana 4`",
    )
    mese: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}$",
        description="Mese nel formato YYYY-MM; se assente usa il mese corrente",
    )
    preview_limit: int = Field(default=5, ge=1, le=20, description="Numero massimo di voci da evidenziare")

    @model_validator(mode="after")
    def validate_request(self) -> "RichiestaInsightObiettivo":
        if self.periodo != "settimana" and self.settimana_iso is not None:
            raise ValueError("`settimana_iso` e' ammesso solo per insight settimanali.")
        if self.periodo != "settimana" and any(value is not None for value in (self.data_da, self.data_a, self.label_periodo)):
            raise ValueError("`data_da`, `data_a` e `label_periodo` sono ammessi solo per insight settimanali.")
        if self.periodo != "mese" and self.mese is not None:
            raise ValueError("`mese` e' ammesso solo per insight mensili.")
        if (self.data_da is None) != (self.data_a is None):
            raise ValueError("Per una settimana custom devi specificare sia `data_da` sia `data_a`.")
        if self.settimana_iso is not None and self.data_da is not None:
            raise ValueError("Non puoi combinare `settimana_iso` con una finestra custom `data_da`/`data_a`.")
        return self
