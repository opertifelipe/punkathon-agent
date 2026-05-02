from __future__ import annotations

_EXPORT_MODULES = {
    "AGENT_NAME": "punkathon_agent.punkagent.constants",
    "SUPPORTED_ATTACHMENT_MIME_TYPES": "punkathon_agent.punkagent.constants",
    "CategoriaSpesa": "punkathon_agent.models.finance",
    "MacroCategoriaSpesa": "punkathon_agent.models.finance",
    "CATEGORIA_TO_MACRO_CATEGORIA": "punkathon_agent.models.finance",
    "MessageContent": "punkathon_agent.models.agent",
    "MovimentoInput": "punkathon_agent.models.agent",
    "FiltroCancellazione": "punkathon_agent.models.agent",
    "ProfiloUtenteUpdate": "punkathon_agent.models.agent",
    "RisparmioInternoUpdate": "punkathon_agent.models.agent",
    "build_chat_model": "punkathon_agent.punkagent.runtime",
    "build_user_message_content": "punkathon_agent.punkagent.attachments",
    "supported_attachment_formats": "punkathon_agent.punkagent.attachments",
    "resolve_attachment_path": "punkathon_agent.punkagent.attachments",
    "aggiungi_movimenti": "punkathon_agent.punkagent.tools",
    "cancella_movimenti": "punkathon_agent.punkagent.tools",
    "ottieni_profilo_utente": "punkathon_agent.punkagent.tools",
    "ottieni_movimenti_mese_corrente": "punkathon_agent.punkagent.tools",
    "riepilogo_movimenti_database": "punkathon_agent.punkagent.tools",
    "aggiorna_profilo_utente": "punkathon_agent.punkagent.tools",
    "aggiorna_risparmio_interno": "punkathon_agent.punkagent.tools",
    "stima_spese_fisse_essenziali": "punkathon_agent.punkagent.tools",
    "analizza_spesa_categorie": "punkathon_agent.punkagent.tools",
    "analizza_budget_attuale": "punkathon_agent.punkagent.tools",
    "analizza_spese_fisse": "punkathon_agent.punkagent.tools",
    "analizza_spese_per_categoria": "punkathon_agent.punkagent.tools",
    "analizza_spese_settimana": "punkathon_agent.punkagent.tools",
    "calcola_budget_residuo_settimana": "punkathon_agent.punkagent.tools",
    "analizza_spese_mese": "punkathon_agent.punkagent.tools",
    "analizza_spese_complessive": "punkathon_agent.punkagent.tools",
    "calcola_spese_fisse_mensili": "punkathon_agent.punkagent.tools",
    "genera_insight_settimanali": "punkathon_agent.punkagent.tools",
    "genera_insight_mensili": "punkathon_agent.punkagent.tools",
    "costruisci_query_sql": "punkathon_agent.punkagent.tools",
    "esegui_query_sql": "punkathon_agent.punkagent.tools",
    "mostra_schema_database": "punkathon_agent.punkagent.tools",
    "mostra_schema_movimenti": "punkathon_agent.punkagent.tools",
    "create_punk_agent": "punkathon_agent.punkagent.runtime",
    "get_punk_agent": "punkathon_agent.punkagent.runtime",
    "create_banking_agent": "punkathon_agent.punkagent.runtime",
    "get_banking_agent": "punkathon_agent.punkagent.runtime",
    "extract_final_answer": "punkathon_agent.punkagent.runtime",
    "serialize_conversation": "punkathon_agent.punkagent.runtime",
    "run_agent_turn": "punkathon_agent.punkagent.runtime",
    "run_agent_turn_streaming": "punkathon_agent.punkagent.runtime",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module = import_module(module_name)
    return getattr(module, name)
