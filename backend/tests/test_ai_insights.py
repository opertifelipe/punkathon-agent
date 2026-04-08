from __future__ import annotations

from datetime import date, datetime, timezone
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from punkathon_agent.cli.api import app
from punkathon_agent.services.ai_insights import (
    SidebarInsightDraft,
    SidebarInsightsLLMOutput,
    _last_three_month_window,
    _normalize_generated_insights,
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

    def test_normalize_generated_insights_caps_buckets_to_two(self) -> None:
        payload = SidebarInsightsLLMOutput(
            positive_insights=[
                SidebarInsightDraft(title="Positivo 1", description="Desc 1"),
                SidebarInsightDraft(title="Positivo 2", description="Desc 2"),
                SidebarInsightDraft(title="Positivo 3", description="Desc 3"),
            ],
            attention_points=[
                SidebarInsightDraft(title="Attenzione 1", description="Desc A"),
                SidebarInsightDraft(title="Attenzione 2", description="Desc B"),
                SidebarInsightDraft(title="Attenzione 3", description="Desc C"),
            ],
        )

        insights = _normalize_generated_insights(
            payload,
            generated_at=datetime(2026, 4, 8, 10, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(sum(1 for item in insights if item["type"] == "success"), 2)
        self.assertEqual(sum(1 for item in insights if item["type"] == "warning"), 2)


class AiInsightsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

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

        response = self.client.post("/insights/generate")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["window_start"], "2026-02-01")
        self.assertEqual(len(body["insights"]), 1)
        mocked_generate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
