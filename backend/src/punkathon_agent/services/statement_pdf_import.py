from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentContentFormat
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import dotenv_values
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from openai import AuthenticationError
from pydantic import BaseModel, Field
from pypdf import PdfReader, PdfWriter

from punkathon_agent.models.agent import MovimentoInput
from punkathon_agent.punkagent.constants import ENV_PATH
from punkathon_agent.punkagent.request_context import (
    get_db_reload_required,
    mark_db_updated,
    reset_current_user_id,
    reset_db_reload_required,
    set_current_user_id,
    set_db_reload_required,
)
from punkathon_agent.punkagent.tools import (
    aggiungi_movimenti,
    calcola_spese_fisse_mensili,
    stima_spese_fisse_essenziali,
)

_FORM_RECOGNIZER_MODEL_ID = "prebuilt-layout"
_FORM_RECOGNIZER_LOCALE = "it-IT"
_DEFAULT_FORM_RECOGNIZER_MAX_CONCURRENCY = 8
_DEFAULT_PAGE_EXTRACTION_MAX_CONCURRENCY = 8
_DEFAULT_PAGE_EXTRACTION_MODEL = "gpt-5.4-mini"


class StatementPageMovements(BaseModel):
    movimenti: list[MovimentoInput] = Field(default_factory=list)


@dataclass(slots=True)
class SplitPdfPage:
    page_number: int
    pdf_bytes: bytes


@dataclass(slots=True)
class OcrPageResult:
    page_number: int
    markdown: str


@dataclass(slots=True)
class PageExtractionResult:
    page_number: int
    movimenti: list[MovimentoInput]


@dataclass(slots=True)
class PdfAttachmentImportResult:
    filename: str
    total_pages: int
    movimenti: list[MovimentoInput]
    ocr_failed_pages: list[int]
    empty_ocr_pages: list[int]
    extraction_failed_pages: list[int]
    pages_without_movements: list[int]


@dataclass(slots=True)
class ProcessedPdfPageResult:
    page_number: int
    movimenti: list[MovimentoInput]
    ocr_failed: bool = False
    empty_ocr: bool = False
    extraction_failed: bool = False
    error: BaseException | None = None


_STATEMENT_PAGE_MOVEMENTS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Sei un parser di estratti conto bancari.

Ricevi il testo OCR di una singola pagina dell'estratto conto bancario.
Devi restituire solo i movimenti bancari reali presenti in quella pagina.

Vincoli obbligatori:
- usa solo dati esplicitamente presenti nel testo OCR della pagina
- restituisci la data in formato YYYY-MM-DD
- usa importi numerici con segno: addebiti e uscite negativi, accrediti e entrate positivi
- pulisci la descrizione, ma senza inventare dettagli
- usa `note` solo se serve davvero a preservare informazione utile presente nella pagina
- ignora saldi iniziali o finali, disponibilita', numeri di pagina, intestazioni, totali, subtotali, IBAN, anagrafiche e riepiloghi
- non duplicare lo stesso movimento nella stessa pagina
- se il testo non contiene movimenti bancari utili, restituisci una lista vuota
- se una riga e' ambigua o incompleta, scartala invece di inventare
- se la valuta usa punti per le migliaia e virgole per i decimali, converti correttamente il numero
""",
        ),
        (
            "human",
            """Nome file: {filename}
Numero pagina: {page_number}

Testo OCR della pagina:
{page_markdown}
""",
        ),
    ]
)


def _resolve_openai_api_key() -> str | None:
    file_key = _env_file_values().get("OPENAI_API_KEY")
    env_key = os.getenv("OPENAI_API_KEY")

    if file_key:
        return str(file_key).strip().strip('"').strip("'")
    if env_key:
        return str(env_key).strip().strip('"').strip("'")
    return None


def _use_responses_api() -> bool:
    raw_value = _resolve_env_value("OPENAI_USE_RESPONSES_API")
    if raw_value is None:
        return False
    return raw_value.casefold() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def _env_file_values() -> dict[str, str | None]:
    return dotenv_values(ENV_PATH)


def _resolve_env_value(*keys: str) -> str | None:
    env_values = _env_file_values()
    for key in keys:
        value = os.getenv(key) or env_values.get(key)
        if value:
            return str(value).strip().strip('"').strip("'")
    return None


def _resolve_max_concurrency(*keys: str, default: int) -> int:
    raw_value = _resolve_env_value(*keys)
    if raw_value is None:
        return default

    try:
        parsed_value = int(raw_value)
    except ValueError:
        return default

    return max(1, parsed_value)


@lru_cache(maxsize=1)
def _form_recognizer_max_concurrency() -> int:
    return _resolve_max_concurrency(
        "STATEMENT_PDF_OCR_MAX_CONCURRENCY",
        default=_DEFAULT_FORM_RECOGNIZER_MAX_CONCURRENCY,
    )


@lru_cache(maxsize=1)
def _page_extraction_max_concurrency() -> int:
    return _resolve_max_concurrency(
        "STATEMENT_PDF_EXTRACTION_MAX_CONCURRENCY",
        default=_DEFAULT_PAGE_EXTRACTION_MAX_CONCURRENCY,
    )


@lru_cache(maxsize=1)
def _page_extraction_model() -> str:
    return _resolve_env_value("STATEMENT_PDF_EXTRACTION_MODEL") or _DEFAULT_PAGE_EXTRACTION_MODEL


@lru_cache(maxsize=1)
def _build_statement_page_extractor() -> Any:
    use_responses_api = _use_responses_api()
    kwargs: dict[str, Any] = {
        "model": _page_extraction_model(),
        "api_key": _resolve_openai_api_key(),
        "use_responses_api": use_responses_api,
        "verbosity": "low",
    }
    if use_responses_api:
        kwargs["output_version"] = "responses/v1"
        kwargs["reasoning"] = {"effort": "none"}
    model = ChatOpenAI(**kwargs)
    return model.with_structured_output(StatementPageMovements)


@lru_cache(maxsize=1)
def _document_intelligence_config() -> tuple[str, str]:
    endpoint = _resolve_env_value(
        "FORM_RECOGNIZER_ENDPOINT",
        "DOCUMENT_INTELLIGENCE_ENDPOINT",
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
    )
    api_key = _resolve_env_value(
        "FORM_RECOGNIZER_KEY",
        "DOCUMENT_INTELLIGENCE_KEY",
        "AZURE_DOCUMENT_INTELLIGENCE_KEY",
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Configurazione Form Recognizer mancante: definisci endpoint e chiave del servizio Azure Document Intelligence."
        )

    return endpoint, api_key


def _create_document_intelligence_client() -> DocumentIntelligenceClient:
    endpoint, api_key = _document_intelligence_config()
    return DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))


def _decode_pdf_attachment(attachment: dict[str, str]) -> bytes:
    filename = attachment.get("filename") or "allegato.pdf"
    try:
        return base64.b64decode(attachment["base64_data"], validate=True)
    except (KeyError, binascii.Error, ValueError) as exc:
        raise ValueError(f"Base64 non valido per l'allegato PDF {filename}.") from exc


def _split_pdf_into_single_page_documents(pdf_bytes: bytes) -> list[SplitPdfPage]:
    reader = PdfReader(BytesIO(pdf_bytes))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover - depends on external PDF encryption details.
            raise ValueError("Il PDF dell'estratto conto e' protetto da password e non posso leggerlo.") from exc

    split_pages: list[SplitPdfPage] = []
    for page_number, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        buffer = BytesIO()
        writer.write(buffer)
        split_pages.append(SplitPdfPage(page_number=page_number, pdf_bytes=buffer.getvalue()))

    return split_pages


def _extract_page_markdown_sync(page_pdf_bytes: bytes) -> str:
    client = _create_document_intelligence_client()
    try:
        poller = client.begin_analyze_document(
            _FORM_RECOGNIZER_MODEL_ID,
            page_pdf_bytes,
            locale=_FORM_RECOGNIZER_LOCALE,
            output_content_format=DocumentContentFormat.MARKDOWN,
        )
        result = poller.result()
    except HttpResponseError as exc:
        raise RuntimeError("Form Recognizer non e' riuscito a leggere una pagina del PDF.") from exc

    return (result.content or "").strip()


async def _extract_page_markdown(page: SplitPdfPage, *, semaphore: asyncio.Semaphore) -> OcrPageResult:
    async with semaphore:
        markdown = await asyncio.to_thread(_extract_page_markdown_sync, page.pdf_bytes)
    return OcrPageResult(page_number=page.page_number, markdown=markdown)


def _first_exception_message(results: list[BaseException]) -> str:
    if not results:
        return "Errore sconosciuto."
    message = str(results[0]).strip()
    return message or results[0].__class__.__name__


def _append_source_note(movimento: MovimentoInput, *, filename: str, page_number: int) -> MovimentoInput:
    source_note = f"Fonte: estratto conto {filename}, pagina {page_number}"
    note_parts = [source_note]
    if movimento.note and movimento.note.strip():
        note_parts.append(movimento.note.strip())

    unique_parts: list[str] = []
    for part in note_parts:
        if part not in unique_parts:
            unique_parts.append(part)

    return movimento.model_copy(update={"note": " | ".join(unique_parts)})


async def _extract_movements_from_page_markdown(
    page: OcrPageResult,
    *,
    filename: str,
    semaphore: asyncio.Semaphore,
) -> PageExtractionResult:
    async with semaphore:
        try:
            chain = _STATEMENT_PAGE_MOVEMENTS_PROMPT | _build_statement_page_extractor()
            payload = await chain.ainvoke(
                {
                    "filename": filename,
                    "page_number": page.page_number,
                    "page_markdown": page.markdown,
                }
            )
        except AuthenticationError as exc:
            raise RuntimeError(
                "Autenticazione OpenAI fallita: verifica che OPENAI_API_KEY sia presente e valida nell'ambiente corrente."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Non sono riuscito a interpretare i movimenti della pagina {page.page_number} di {filename}."
            ) from exc

    return PageExtractionResult(page_number=page.page_number, movimenti=payload.movimenti)


async def _process_pdf_page(
    page: SplitPdfPage,
    *,
    filename: str,
    ocr_semaphore: asyncio.Semaphore,
    extraction_semaphore: asyncio.Semaphore,
) -> ProcessedPdfPageResult:
    try:
        ocr_result = await _extract_page_markdown(page, semaphore=ocr_semaphore)
    except BaseException as exc:
        return ProcessedPdfPageResult(
            page_number=page.page_number,
            movimenti=[],
            ocr_failed=True,
            error=exc,
        )

    if not ocr_result.markdown.strip():
        return ProcessedPdfPageResult(
            page_number=page.page_number,
            movimenti=[],
            empty_ocr=True,
        )

    try:
        extraction_result = await _extract_movements_from_page_markdown(
            ocr_result,
            filename=filename,
            semaphore=extraction_semaphore,
        )
    except BaseException as exc:
        return ProcessedPdfPageResult(
            page_number=page.page_number,
            movimenti=[],
            extraction_failed=True,
            error=exc,
        )

    return ProcessedPdfPageResult(
        page_number=page.page_number,
        movimenti=extraction_result.movimenti,
    )


async def _process_pdf_attachment(
    attachment: dict[str, str],
    *,
    ocr_semaphore: asyncio.Semaphore,
    extraction_semaphore: asyncio.Semaphore,
) -> PdfAttachmentImportResult:
    filename = attachment.get("filename") or "statement.pdf"
    pdf_bytes = _decode_pdf_attachment(attachment)
    split_pages = _split_pdf_into_single_page_documents(pdf_bytes)

    if not split_pages:
        return PdfAttachmentImportResult(
            filename=filename,
            total_pages=0,
            movimenti=[],
            ocr_failed_pages=[],
            empty_ocr_pages=[],
            extraction_failed_pages=[],
            pages_without_movements=[],
        )

    page_outcomes = await asyncio.gather(
        *[
            _process_pdf_page(
                page,
                filename=filename,
                ocr_semaphore=ocr_semaphore,
                extraction_semaphore=extraction_semaphore,
            )
            for page in split_pages
        ]
    )

    ocr_failed_pages: list[int] = []
    empty_ocr_pages: list[int] = []
    ocr_errors: list[BaseException] = []

    movimenti: list[MovimentoInput] = []
    extraction_failed_pages: list[int] = []
    pages_without_movements: list[int] = []
    extraction_errors: list[BaseException] = []

    readable_ocr_pages = 0

    for outcome in page_outcomes:
        if outcome.ocr_failed:
            ocr_failed_pages.append(outcome.page_number)
            if outcome.error is not None:
                ocr_errors.append(outcome.error)
            continue
        if outcome.empty_ocr:
            empty_ocr_pages.append(outcome.page_number)
            continue

        readable_ocr_pages += 1

        if outcome.extraction_failed:
            extraction_failed_pages.append(outcome.page_number)
            if outcome.error is not None:
                extraction_errors.append(outcome.error)
            continue

        if not outcome.movimenti:
            pages_without_movements.append(outcome.page_number)
            continue

        movimenti.extend(
            _append_source_note(movimento, filename=filename, page_number=outcome.page_number)
            for movimento in outcome.movimenti
        )

    if not readable_ocr_pages and ocr_errors:
        raise RuntimeError(
            f"Form Recognizer non e' riuscito a leggere nessuna pagina di {filename}: {_first_exception_message(ocr_errors)}"
        )

    if readable_ocr_pages and not movimenti and extraction_errors and len(extraction_failed_pages) == readable_ocr_pages:
        raise RuntimeError(
            f"Non sono riuscito a estrarre movimenti da nessuna pagina OCR di {filename}: "
            f"{_first_exception_message(extraction_errors)}"
        )

    return PdfAttachmentImportResult(
        filename=filename,
        total_pages=len(split_pages),
        movimenti=movimenti,
        ocr_failed_pages=ocr_failed_pages,
        empty_ocr_pages=empty_ocr_pages,
        extraction_failed_pages=extraction_failed_pages,
        pages_without_movements=pages_without_movements,
    )


def _save_movements(movimenti: list[MovimentoInput]) -> tuple[dict[str, Any], bool]:
    payload = json.loads(aggiungi_movimenti(movimenti))
    changed = any(
        int(payload.get(field, 0) or 0) > 0
        for field in (
            "aggiunti",
            "duplicati_esatti_gestiti",
            "duplicati_cross_source_rimossi",
        )
    )
    return payload, changed


def _page_list_label(page_numbers: list[int]) -> str:
    return ", ".join(str(page_number) for page_number in page_numbers)


def _build_summary(
    results: list[PdfAttachmentImportResult],
    *,
    saved_payload: dict[str, Any] | None,
    fixed_expense_message: str | None,
) -> str:
    total_pages = sum(result.total_pages for result in results)
    total_movements = sum(len(result.movimenti) for result in results)
    lines = [
        (
            "Import PDF completato: "
            f"{len(results)} file, {total_pages} pagine analizzate, {total_movements} movimenti estratti."
        )
    ]

    if saved_payload is not None:
        lines.append(
            "Salvataggio movimenti: "
            f"{int(saved_payload.get('aggiunti', 0) or 0)} nuovi, "
            f"{int(saved_payload.get('duplicati_esatti_gestiti', 0) or 0)} duplicati esatti gestiti, "
            f"{int(saved_payload.get('duplicati_cross_source_rimossi', 0) or 0)} duplicati cross-source rimossi."
        )
    else:
        lines.append("Salvataggio movimenti: nessun movimento utile trovato nei PDF.")

    for result in results:
        details = [
            f"{result.total_pages} pagine",
            f"{len(result.movimenti)} movimenti",
        ]
        if result.ocr_failed_pages:
            details.append(f"OCR fallito su pagine {_page_list_label(result.ocr_failed_pages)}")
        if result.empty_ocr_pages:
            details.append(f"nessun testo utile su pagine {_page_list_label(result.empty_ocr_pages)}")
        if result.extraction_failed_pages:
            details.append(
                f"estrazione fallita su pagine {_page_list_label(result.extraction_failed_pages)}"
            )
        if result.pages_without_movements:
            details.append(
                f"nessun movimento trovato su pagine {_page_list_label(result.pages_without_movements)}"
            )
        lines.append(f"- {result.filename}: {', '.join(details)}")

    if fixed_expense_message:
        lines.append(f"Spese fisse: {fixed_expense_message}")

    return "\n".join(lines)


async def import_statement_pdf_attachments(
    attachments: list[dict[str, str]],
    *,
    user_id: int,
) -> tuple[str, bool]:
    pdf_attachments = [attachment for attachment in attachments if attachment.get("mime_type") == "application/pdf"]
    if not pdf_attachments:
        return "", False

    user_token = set_current_user_id(user_id)
    reload_token = set_db_reload_required(False)
    try:
        ocr_semaphore = asyncio.Semaphore(_form_recognizer_max_concurrency())
        extraction_semaphore = asyncio.Semaphore(_page_extraction_max_concurrency())

        results = await asyncio.gather(
            *[
                _process_pdf_attachment(
                    attachment,
                    ocr_semaphore=ocr_semaphore,
                    extraction_semaphore=extraction_semaphore,
                )
                for attachment in pdf_attachments
            ]
        )

        all_movements = [movimento for result in results for movimento in result.movimenti]
        saved_payload: dict[str, Any] | None = None

        if all_movements:
            saved_payload, changed = await asyncio.to_thread(_save_movements, all_movements)
            if changed:
                mark_db_updated()

        fixed_expenses_message: str | None = None
        fixed_expenses_payload = json.loads(stima_spese_fisse_essenziali(sovrascrivi_valore_esistente=True))
        fixed_expenses_message = str(fixed_expenses_payload.get("message") or "").strip() or None
        calcola_spese_fisse_mensili()

        return _build_summary(
            results,
            saved_payload=saved_payload,
            fixed_expense_message=fixed_expenses_message,
        ), get_db_reload_required()
    finally:
        reset_db_reload_required(reload_token)
        reset_current_user_id(user_token)