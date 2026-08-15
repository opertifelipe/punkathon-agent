from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from punkathon_agent.cli.api import app, get_current_user
from punkathon_agent.db import engine as app_engine
from punkathon_agent.models.db import PunkUser
from punkathon_agent.punkagent.attachments import build_user_message_content
from punkathon_agent.punkagent.request_context import reset_frontend_context, set_frontend_context
from punkathon_agent.services.spending import _inject_profile_context, resolve_week_window


FRONTEND_CONTEXT = {
    "weekly_overview": {
        "month_start": "2026-04-01",
        "month_label": "Aprile 2026",
        "default_week_index": 2,
        "weeks": [
            {
                "index": 1,
                "label": "Settimana 1",
                "start": "2026-04-01",
                "end": "2026-04-07",
                "total": 110.0,
                "contains_today": False,
            },
            {
                "index": 2,
                "label": "Settimana 2",
                "start": "2026-04-08",
                "end": "2026-04-14",
                "total": 95.0,
                "contains_today": True,
            },
        ],
    }
}


class FrontendWeekContextTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: PunkUser(
            id=1,
            email="frontend@example.com",
            nome="Mario",
            cognome="Rossi",
            eta=33,
            password_hash="not-used-in-tests",
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        app_engine.dispose()

    def test_build_user_message_content_includes_frontend_weekly_overview(self) -> None:
        content = build_user_message_content(
            "Fammi l'analisi della settimana",
            frontend_context=FRONTEND_CONTEXT,
        )

        self.assertIsInstance(content, str)
        self.assertIn("Contesto frontend corrente del riquadro settimanale in basso", content)
        self.assertIn("Settimana 2: 2026-04-08 -> 2026-04-14", content)

    def test_resolve_week_window_uses_frontend_default_week(self) -> None:
        token = set_frontend_context(FRONTEND_CONTEXT)
        try:
            window = resolve_week_window(today=date(2026, 4, 8))
        finally:
            reset_frontend_context(token)

        self.assertEqual(window["label"], "Settimana 2")
        self.assertEqual(window["start_date"].isoformat(), "2026-04-08")
        self.assertEqual(window["end_date"].isoformat(), "2026-04-14")

    @patch("punkathon_agent.services.spending._current_user_profile_snapshot")
    def test_injected_profile_context_mentions_how_to_add_first_movements(
        self,
        mocked_snapshot: unittest.mock.Mock,
    ) -> None:
        mocked_snapshot.return_value = {
            "utente_autenticato": {
                "id": 1,
                "nome": "Mario",
                "cognome": "Rossi",
                "nome_completo": "Mario Rossi",
                "eta": 33,
            },
            "conteggio_movimenti_database": 0,
            "database_movimenti_vuoto": True,
            "profilo": {},
            "campi_mancanti": [],
            "stato_spese_fisse_essenziali": "non_stimabili_dai_movimenti",
        }

        content = _inject_profile_context("Ciao")

        self.assertIsInstance(content, str)
        self.assertIn("database dei movimenti bancari e' ancora vuoto", content)
        self.assertIn("PDF dell'estratto conto", content)
        self.assertIn("foto di scontrini o ricevute", content)
        self.assertIn("scrivendoli direttamente in chat", content)

    @patch("punkathon_agent.cli.api.get_punk_agent")
    @patch("punkathon_agent.cli.api.run_agent_turn")
    def test_chat_endpoint_forwards_frontend_context(
        self,
        mocked_run_agent_turn: unittest.mock.Mock,
        mocked_get_punk_agent: unittest.mock.Mock,
    ) -> None:
        mocked_get_punk_agent.return_value = object()
        mocked_run_agent_turn.return_value = ("ok", [], False)

        response = self.client.post(
            "/chat",
            json={
                "message": "Analizza la settimana mostrata sotto",
                "conversation": [],
                "attachments": [],
                "frontend_context": FRONTEND_CONTEXT,
            },
        )

        self.assertEqual(response.status_code, 200)
        mocked_run_agent_turn.assert_called_once()
        self.assertFalse(response.json()["reload"])
        self.assertEqual(
            mocked_run_agent_turn.call_args.kwargs["frontend_context"],
            FRONTEND_CONTEXT,
        )

    @patch("punkathon_agent.cli.api.get_punk_agent")
    @patch("punkathon_agent.cli.api.run_agent_turn")
    @patch("punkathon_agent.cli.api.import_statement_pdf_attachments", new_callable=AsyncMock)
    def test_chat_endpoint_auto_imports_attachments_before_answer(
        self,
        mocked_import_statement_pdf_attachments: AsyncMock,
        mocked_run_agent_turn: unittest.mock.Mock,
        mocked_get_punk_agent: unittest.mock.Mock,
    ) -> None:
        mocked_get_punk_agent.return_value = object()
        mocked_import_statement_pdf_attachments.return_value = ("pdf import ok", True)
        mocked_run_agent_turn.return_value = ("risposta finale", [], False)

        response = self.client.post(
            "/chat",
            json={
                "message": "",
                "conversation": [],
                "attachments": [
                    {
                        "filename": "statement.pdf",
                        "mime_type": "application/pdf",
                        "base64_data": "ZmFrZS1wZGY=",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        mocked_import_statement_pdf_attachments.assert_awaited_once()
        self.assertEqual(mocked_run_agent_turn.call_count, 1)
        visible_call = mocked_run_agent_turn.call_args

        self.assertEqual(visible_call.kwargs["inline_attachments"], [])
        self.assertIn("tentativo di import automatico", visible_call.args[2])
        self.assertTrue(response.json()["reload"])

    @patch("punkathon_agent.cli.api.get_punk_agent")
    @patch("punkathon_agent.cli.api.run_agent_turn")
    @patch("punkathon_agent.cli.api.import_statement_pdf_attachments", new_callable=AsyncMock)
    def test_chat_endpoint_keeps_image_attachments_on_legacy_import_path(
        self,
        mocked_import_statement_pdf_attachments: AsyncMock,
        mocked_run_agent_turn: unittest.mock.Mock,
        mocked_get_punk_agent: unittest.mock.Mock,
    ) -> None:
        mocked_get_punk_agent.return_value = object()
        mocked_run_agent_turn.side_effect = [
            ("import immagine ok", [], True),
            ("risposta finale", [], False),
        ]

        response = self.client.post(
            "/chat",
            json={
                "message": "",
                "conversation": [],
                "attachments": [
                    {
                        "filename": "receipt.png",
                        "mime_type": "image/png",
                        "base64_data": "ZmFrZS1pbWFnZQ==",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        mocked_import_statement_pdf_attachments.assert_not_awaited()
        self.assertEqual(mocked_run_agent_turn.call_count, 2)
        preload_call = mocked_run_agent_turn.call_args_list[0]
        visible_call = mocked_run_agent_turn.call_args_list[1]

        self.assertEqual(preload_call.args[1], [])
        self.assertEqual(preload_call.kwargs["inline_attachments"][0]["filename"], "receipt.png")
        self.assertEqual(visible_call.kwargs["inline_attachments"], [])
        self.assertTrue(response.json()["reload"])


if __name__ == "__main__":
    unittest.main()
