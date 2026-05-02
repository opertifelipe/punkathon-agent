from __future__ import annotations

_EXPORT_MODULES = {
    "AggregazioneQuerySQL": "punkathon_agent.models.agent",
    "ApiAttachment": "punkathon_agent.models.api",
    "BatchClassificazioneMovimenti": "punkathon_agent.models.finance",
    "CATEGORIA_TO_MACRO_CATEGORIA": "punkathon_agent.models.finance",
    "CategoriaSpesa": "punkathon_agent.models.finance",
    "ChatRequest": "punkathon_agent.models.api",
    "ChatResponse": "punkathon_agent.models.api",
    "ClassificazioneMovimento": "punkathon_agent.models.finance",
    "ClassificazioneMovimentoIndicizzata": "punkathon_agent.models.finance",
    "FiltroCancellazione": "punkathon_agent.models.agent",
    "FiltroQuerySQL": "punkathon_agent.models.agent",
    "MacroCategoriaSpesa": "punkathon_agent.models.finance",
    "MessageContent": "punkathon_agent.models.agent",
    "MovimentoBancario": "punkathon_agent.models.db",
    "MovimentoInput": "punkathon_agent.models.agent",
    "OrdinamentoQuerySQL": "punkathon_agent.models.agent",
    "PeriodoAnalisi": "punkathon_agent.models.agent",
    "PunkUser": "punkathon_agent.models.db",
    "ProfiloUtenteUpdate": "punkathon_agent.models.agent",
    "RichiestaAnalisiCategorieSpesa": "punkathon_agent.models.agent",
    "RichiestaAnalisiMese": "punkathon_agent.models.agent",
    "RichiestaAnalisiPerCategoria": "punkathon_agent.models.agent",
    "RichiestaAnalisiSettimana": "punkathon_agent.models.agent",
    "RichiestaAnalisiStorica": "punkathon_agent.models.agent",
    "RichiestaCostruzioneQuerySQL": "punkathon_agent.models.agent",
    "RichiestaInsightObiettivo": "punkathon_agent.models.agent",
    "RisparmioInternoUpdate": "punkathon_agent.models.agent",
    "Utente": "punkathon_agent.models.db",
    "serialize_classification_schema": "punkathon_agent.models.finance",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module = import_module(module_name)
    return getattr(module, name)
