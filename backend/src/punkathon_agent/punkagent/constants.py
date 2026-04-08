from __future__ import annotations

from pathlib import Path

AGENT_NAME = "PunkAgent"
DEEPAGENTS_AGENT_NAME = "punkagent"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEEPAGENTS_BACKEND_ROOT = PACKAGE_ROOT
ENV_PATH = PROJECT_ROOT / ".env"
DEEPAGENTS_SKILL_SOURCES = ["/skills/project/"]
MAX_QUERY_ROWS = 200
SUPPORTED_ATTACHMENT_MIME_TYPES = {
    "application/pdf",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ESSENTIAL_FIXED_KEYWORDS = {
    "affitto",
    "mutuo",
    "condominio",
    "acqua",
    "gas",
    "luce",
    "energia",
    "elettric",
    "iren",
    "enel",
    "acea",
    "a2a",
    "sorgenia",
    "illumia",
    "fastweb",
    "telefono",
    "internet",
    "fibra",
    "vodafone",
    "iliad",
    "wind",
    "tim",
}
RECURRING_FIXED_HINTS = {"addebito diretto", "mandato", "bonifico", "domiciliazione", "rid"}
DESCRIPTION_STOPWORDS = {
    "addebito",
    "al",
    "alla",
    "banca",
    "bancomat",
    "bonifico",
    "carta",
    "conto",
    "corso",
    "disposto",
    "diretto",
    "europe",
    "favore",
    "fonte",
    "foto",
    "gruppo",
    "mandato",
    "mercato",
    "pagamento",
    "pdf",
    "scontrino",
    "societa",
    "spa",
    "srl",
    "torino",
    "transazione",
    "via",
}
STATEMENT_SOURCE_HINTS = {"estratto conto", ".pdf", "pdf", "contabilizzato", "fonte: estratto conto"}
RECEIPT_SOURCE_HINTS = {"scontrino", "ricevuta", "foto_", "fonte: scontrino", "fonte: foto"}