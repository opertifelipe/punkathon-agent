from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from punkathon_agent.cli.api import app
from punkathon_agent.punkagent.attachments import build_user_message_content
from punkathon_agent.punkagent.request_context import reset_frontend_context, set_frontend_context
from punkathon_agent.services.spending import resolve_week_window


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
        self.client = TestClient(app)

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

    @patch("punkathon_agent.cli.api.run_agent_turn")
    def test_chat_endpoint_forwards_frontend_context(self, mocked_run_agent_turn: unittest.mock.Mock) -> None:
        mocked_run_agent_turn.return_value = ("ok", [])

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
        self.assertEqual(
            mocked_run_agent_turn.call_args.kwargs["frontend_context"],
            FRONTEND_CONTEXT,
        )


if __name__ == "__main__":
    unittest.main()
