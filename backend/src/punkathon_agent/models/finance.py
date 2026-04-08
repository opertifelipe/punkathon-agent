from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class MacroCategoriaSpesa(str, Enum):
    """Macro-categorie disponibili per classificare una transazione."""

    SPESE_FISSE = "Spese Fisse"
    SPESE_VARIABILI = "Spese Variabili"
    ENTRATE = "Entrate"


class CategoriaSpesa(str, Enum):
    """Categorie disponibili per classificare una transazione."""

    AFFITTO_O_MUTUO = "Affitto o Mutuo"
    CONDOMINIO = "Condominio"
    ACQUA = "Acqua"
    GAS = "Gas"
    LUCE = "Luce"
    TELEFONO_INTERNET = "Telefono / Internet"
    ASSICURAZIONI = "Assicurazioni"
    MACCHINA = "Macchina"
    PALESTRA = "Palestra"
    ABBONAMENTI = "Abbonamenti"
    ALIMENTAZIONE = "Alimentazione"
    SPESE_MEDICHE = "Spese Mediche"
    FARMACIA = "Farmacia"
    TRASPORTO = "Trasporto"
    RISTORANTI = "Ristoranti"
    BAR = "Bar"
    DELIVERY = "Delivery"
    CULTURALE = "Culturale"
    VESTITI = "Vestiti"
    FIGLI = "Figli"
    PET = "Pet"
    AMAZON = "Amazon"
    ALTRO_NON_ESSENZIALE = "Altro Non Essenziale"
    ENTRATE = "Entrate"


CATEGORIA_TO_MACRO_CATEGORIA = {
    CategoriaSpesa.AFFITTO_O_MUTUO: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.CONDOMINIO: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.ACQUA: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.GAS: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.LUCE: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.TELEFONO_INTERNET: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.ASSICURAZIONI: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.MACCHINA: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.PALESTRA: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.ABBONAMENTI: MacroCategoriaSpesa.SPESE_FISSE,
    CategoriaSpesa.ALIMENTAZIONE: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.SPESE_MEDICHE: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.FARMACIA: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.TRASPORTO: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.RISTORANTI: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.BAR: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.DELIVERY: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.CULTURALE: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.VESTITI: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.FIGLI: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.PET: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.AMAZON: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.ALTRO_NON_ESSENZIALE: MacroCategoriaSpesa.SPESE_VARIABILI,
    CategoriaSpesa.ENTRATE: MacroCategoriaSpesa.ENTRATE,
}


class ClassificazioneMovimento(BaseModel):
    categoria: CategoriaSpesa
    macrocategoria: MacroCategoriaSpesa

    @model_validator(mode="after")
    def validate_categoria_mapping(self) -> "ClassificazioneMovimento":
        expected = CATEGORIA_TO_MACRO_CATEGORIA[self.categoria]
        if self.macrocategoria != expected:
            raise ValueError(
                f"La macrocategoria {self.macrocategoria.value!r} non e' valida per {self.categoria.value!r}."
            )
        return self


class ClassificazioneMovimentoIndicizzata(ClassificazioneMovimento):
    indice: int = Field(ge=0)


class BatchClassificazioneMovimenti(BaseModel):
    classificazioni: list[ClassificazioneMovimentoIndicizzata] = Field(
        description="Una classificazione per ciascun indice fornito in input."
    )


def serialize_classification_schema() -> dict[str, Any]:
    return {
        "macrocategorie": [item.value for item in MacroCategoriaSpesa],
        "categorie": [item.value for item in CategoriaSpesa],
        "mappa_categoria_macrocategoria": {
            categoria.value: CATEGORIA_TO_MACRO_CATEGORIA[categoria].value for categoria in CategoriaSpesa
        },
    }
