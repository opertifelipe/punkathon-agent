from __future__ import annotations

from datetime import date, datetime, timezone
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from punkathon_agent.cli.api import app
from punkathon_agent.services.ai_insights import (
    SidebarInsightDraft,
    SidebarInsightsLLMOutput,
    _last_three_month_window,
    _normalize_generated_insights,
    generate_goal_based_sidebar_insights,
)


class AiInsightsServiceTests(unittest.TestCase):
    def test_last_three_month_window_covers_current_and_previous_two_months(self) -> None:
        window = _last_three_month_window(date(2026, 4, 8))

        self.assertEqual(window["start_date"].isoformat(), "2026-02-01")
        self.assertEqual(window["end_date"].isoformat(), "2026-04-08")
        self.assertEqual(
            [item["label"] for item in window["month_windows"]],
            ["2026-02", "2026-03", "2026-04"],
        )

    def test_normalize_generated_insights_caps_buckets_to_three(self) -> None:
        payload = SidebarInsightsLLMOutput(
            positive_insights=[
                SidebarInsightDraft(title="Positivo 1", description="Desc 1"),
                SidebarInsightDraft(title="Positivo 2", description="Desc 2"),
                SidebarInsightDraft(title="Positivo 3", description="Desc 3"),
                SidebarInsightDraft(title="Positivo 4", description="Desc 4"),
            ],
            attention_points=[
                SidebarInsightDraft(title="Attenzione 1", description="Desc A"),
                SidebarInsightDraft(title="Attenzione 2", description="Desc B"),
                SidebarInsightDraft(title="Attenzione 3", description="Desc C"),
                SidebarInsightDraft(title="Attenzione 4", description="Desc D"),
            ],
        )

        insights = _normalize_generated_insights(
            payload,
            generated_at=datetime(2026, 4, 8, 10, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(sum(1 for item in insights if item["type"] == "success"), 3)
        self.assertEqual(sum(1 for item in insights if item["type"] == "warning"), 3)

    @patch("punkathon_agent.services.ai_insights._invoke_sidebar_insights_model")
    @patch("punkathon_agent.services.ai_insights._build_recent_context")
    @patch("punkathon_agent.services.ai_insights._fetch_movements_between")
    @patch("punkathon_agent.services.ai_insights._fetch_all_movements")
    @patch("punkathon_agent.services.ai_insights._sync_budget_fields")
    @patch("punkathon_agent.services.ai_insights._get_or_create_user_profile")
    @patch("punkathon_agent.services.ai_insights.get_session")
    @patch("punkathon_agent.services.ai_insights.create_database")
    def test_generate_goal_based_sidebar_insights_passes_user_id_to_fetches(
        self,
        _mock_create_database: MagicMock,
        mock_get_session: MagicMock,
        mock_get_profile: MagicMock,
        _mock_sync_budget_fields: MagicMock,
        mock_fetch_all_movements: MagicMock,
        mock_fetch_movements_between: MagicMock,
        mock_build_recent_context: MagicMock,
        mock_invoke_model: MagicMock,
    ) -> None:
        fake_session = object()
        mock_get_session.return_value.__enter__.return_value = fake_session
        mock_get_profile.return_value = MagicMock()
        mock_fetch_all_movements.return_value = []
        mock_fetch_movements_between.return_value = []
        mock_build_recent_context.return_value = {"ok": True}
        mock_invoke_model.return_value = SidebarInsightsLLMOutput()

        generate_goal_based_sidebar_insights(reference_date=date(2026, 4, 8), user_id=123)

        mock_get_profile.assert_called_once_with(fake_session, user_id=123)
        mock_fetch_all_movements.assert_called_once_with(fake_session, user_id=123)
        mock_fetch_movements_between.assert_called_once()
        self.assertEqual(mock_fetch_movements_between.call_args.kwargs["user_id"], 123)


class AiInsightsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    @patch("punkathon_agent.cli.api.generate_goal_based_sidebar_insights")
    def test_generate_insights_endpoint_returns_payload(self, mocked_generate: unittest.mock.Mock) -> None:
        mocked_generate.return_value = {
            "generated_at": "2026-04-08T10:30:00+00:00",
            "window_start": "2026-02-01",
            "window_end": "2026-04-08",
            "insights": [
                {
                    "id": "abc",
                    "type": "success",
                    "title": "Trend sotto controllo",
                    "description": "Le spese variabili sono scese nell'ultimo mese.",
                    "timestamp": "2026-04-08T10:30:00+00:00",
                }
            ],
        }

        signup_response = self.client.post(
            "/auth/signup",
            json={
                "email": f"insights-{uuid4().hex[:8]}@example.com",
                "nome": "Iris",
                "cognome": "Test",
                "eta": 23,
                "password": "password123",
            },
        )
        token = signup_response.json()["access_token"]

        response = self.client.post(
            "/insights/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["window_start"], "2026-02-01")
        self.assertEqual(len(body["insights"]), 1)
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertIn("user_id", mocked_generate.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
