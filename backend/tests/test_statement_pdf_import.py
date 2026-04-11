from __future__ import annotations

import base64
from datetime import date
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

from punkathon_agent.models.agent import MovimentoInput
from punkathon_agent.services.statement_pdf_import import (
    OcrPageResult,
    PageExtractionResult,
    _split_pdf_into_single_page_documents,
    import_statement_pdf_attachments,
)


def _build_pdf_bytes(page_count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class StatementPdfSplitTests(unittest.TestCase):
    def test_split_pdf_into_single_page_documents_returns_one_pdf_per_page(self) -> None:
        pdf_bytes = _build_pdf_bytes(3)

        split_pages = _split_pdf_into_single_page_documents(pdf_bytes)

        self.assertEqual(len(split_pages), 3)
        for expected_page_number, split_page in enumerate(split_pages, start=1):
            self.assertEqual(split_page.page_number, expected_page_number)
            self.assertEqual(len(PdfReader(BytesIO(split_page.pdf_bytes)).pages), 1)


class StatementPdfImportTests(unittest.IsolatedAsyncioTestCase):
    @patch("punkathon_agent.services.statement_pdf_import.calcola_spese_fisse_mensili")
    @patch("punkathon_agent.services.statement_pdf_import.stima_spese_fisse_essenziali")
    @patch("punkathon_agent.services.statement_pdf_import.aggiungi_movimenti")
    @patch("punkathon_agent.services.statement_pdf_import._extract_movements_from_page_markdown")
    @patch("punkathon_agent.services.statement_pdf_import._extract_page_markdown")
    async def test_import_statement_pdf_attachments_saves_page_source_notes_with_parallel_ocr(
        self,
        mocked_extract_page_markdown: unittest.mock.AsyncMock,
        mocked_extract_movements_from_page_markdown: unittest.mock.AsyncMock,
        mocked_aggiungi_movimenti: unittest.mock.Mock,
        mocked_stima_spese_fisse_essenziali: unittest.mock.Mock,
        mocked_calcola_spese_fisse_mensili: unittest.mock.Mock,
    ) -> None:
        pdf_bytes = _build_pdf_bytes(2)
        attachment = {
            "filename": "statement.pdf",
            "mime_type": "application/pdf",
            "base64_data": base64.b64encode(pdf_bytes).decode("utf-8"),
        }

        async def fake_extract_page_markdown(page, *, semaphore):
            return OcrPageResult(page_number=page.page_number, markdown=f"pagina {page.page_number}")

        async def fake_extract_movements_from_page_markdown(page, *, filename, semaphore):
            note = "riga OCR utile" if page.page_number == 1 else None
            return PageExtractionResult(
                page_number=page.page_number,
                movimenti=[
                    MovimentoInput(
                        data=date(2026, 4, page.page_number),
                        descrizione=f"Movimento {page.page_number}",
                        importo=-10.0 * page.page_number,
                        note=note,
                    )
                ],
            )

        mocked_extract_page_markdown.side_effect = fake_extract_page_markdown
        mocked_extract_movements_from_page_markdown.side_effect = fake_extract_movements_from_page_markdown
        mocked_aggiungi_movimenti.return_value = json.dumps(
            {
                "aggiunti": 2,
                "duplicati_esatti_gestiti": 0,
                "duplicati_cross_source_rimossi": 0,
            }
        )
        mocked_stima_spese_fisse_essenziali.return_value = json.dumps(
            {"message": "Spese fisse sincronizzate con successo."}
        )
        mocked_calcola_spese_fisse_mensili.return_value = json.dumps({"message": "ok"})

        summary, reload_required = await import_statement_pdf_attachments([attachment], user_id=7)

        self.assertTrue(reload_required)
        self.assertIn("2 pagine analizzate", summary)
        self.assertIn("2 movimenti estratti", summary)
        self.assertIn("statement.pdf: 2 pagine, 2 movimenti", summary)

        mocked_aggiungi_movimenti.assert_called_once()
        saved_movements = mocked_aggiungi_movimenti.call_args.args[0]
        self.assertEqual(len(saved_movements), 2)
        self.assertEqual(saved_movements[0].note, "Fonte: estratto conto statement.pdf, pagina 1 | riga OCR utile")
        self.assertEqual(saved_movements[1].note, "Fonte: estratto conto statement.pdf, pagina 2")

        mocked_stima_spese_fisse_essenziali.assert_called_once_with(sovrascrivi_valore_esistente=True)
        mocked_calcola_spese_fisse_mensili.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()