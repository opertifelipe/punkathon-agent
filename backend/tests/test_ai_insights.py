from __future__ import annotations

from datetime import date, datetime, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from punkathon_agent.cli.api import app
from punkathon_agent.services.ai_insights import (
    SidebarInsightDraft,
    SidebarInsightsLLMOutput,
    _fallback_single_insight,
    _last_three_month_window,
    _normalize_generated_insights,
    _normalize_single_insight,
    get_sidebar_insights_availability,
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

    def test_normalize_generated_insights_keeps_sidebar_copy_short(self) -> None:
        long_description = " ".join(["spesa"] * 50)
        payload = SidebarInsightsLLMOutput(
            positive_insights=[SidebarInsightDraft(title="Positivo", description=long_description)],
        )

        insights = _normalize_generated_insights(
            payload,
            generated_at=datetime(2026, 4, 8, 10, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(len(insights), 1)
        self.assertTrue(insights[0]["description"].endswith("..."))
        self.assertLessEqual(len(insights[0]["description"]), 220)

    def test_normalize_single_insight_uses_type_specific_fallback_when_empty(self) -> None:
        generated_at = datetime(2026, 4, 8, 10, 30, tzinfo=timezone.utc)

        success_insight = _normalize_single_insight(
            SidebarInsightDraft(title="  ok  ", description="  bene  "),
            insight_type="success",
            generated_at=generated_at,
        )
        warning_fallback = _normalize_single_insight(
            SidebarInsightDraft(title="   ", description="   "),
            insight_type="warning",
            generated_at=generated_at,
        )
        expected_warning_fallback = _fallback_single_insight(
            insight_type="warning",
            generated_at=generated_at,
        )

        self.assertEqual(success_insight["type"], "success")
        self.assertEqual(success_insight["title"], "ok")
        self.assertEqual(success_insight["description"], "bene")
        self.assertEqual(warning_fallback["type"], expected_warning_fallback["type"])
        self.assertEqual(warning_fallback["title"], expected_warning_fallback["title"])
        self.assertEqual(warning_fallback["description"], expected_warning_fallback["description"])
        self.assertEqual(warning_fallback["timestamp"], expected_warning_fallback["timestamp"])

    def test_normalize_single_insight_preserves_longer_popup_description(self) -> None:
        generated_at = datetime(2026, 4, 8, 10, 30, tzinfo=timezone.utc)
        long_description = " ".join(["margine"] * 45)

        insight = _normalize_single_insight(
            SidebarInsightDraft(title="Conti in ordine", description=long_description),
            insight_type="success",
            generated_at=generated_at,
        )

        self.assertEqual(insight["description"], long_description)
        self.assertGreater(len(insight["description"]), 220)

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
        mock_build_recent_context.return_value = {
            "movimenti_ultimi_3_mesi": {
                "conteggio_movimenti": 1,
            }
        }
        mock_invoke_model.return_value = SidebarInsightsLLMOutput()

        generate_goal_based_sidebar_insights(reference_date=date(2026, 4, 8), user_id=123)

        mock_get_profile.assert_called_once_with(fake_session, user_id=123)
        mock_fetch_all_movements.assert_called_once_with(fake_session, user_id=123)
        mock_fetch_movements_between.assert_called_once()
        self.assertEqual(mock_fetch_movements_between.call_args.kwargs["user_id"], 123)

    @patch("punkathon_agent.services.ai_insights._invoke_sidebar_insights_model")
    @patch("punkathon_agent.services.ai_insights._load_sidebar_insights_context")
    def test_generate_goal_based_sidebar_insights_skips_llm_when_no_recent_records(
        self,
        mock_load_context: MagicMock,
        mock_invoke_model: MagicMock,
    ) -> None:
        mock_load_context.return_value = (
            {
                "movimenti_ultimi_3_mesi": {
                    "conteggio_movimenti": 0,
                }
            },
            {
                "start_date": date(2026, 2, 1),
                "end_date": date(2026, 4, 8),
            },
        )

        payload = generate_goal_based_sidebar_insights(reference_date=date(2026, 4, 8), user_id=123)

        self.assertFalse(payload["has_recent_records"])
        self.assertEqual(payload["recent_records_count"], 0)
        self.assertEqual(payload["insights"], [])
        mock_invoke_model.assert_not_called()

    @patch("punkathon_agent.services.ai_insights._fetch_movements_between")
    @patch("punkathon_agent.services.ai_insights.get_session")
    @patch("punkathon_agent.services.ai_insights.create_database")
    def test_get_sidebar_insights_availability_reports_recent_records(
        self,
        _mock_create_database: MagicMock,
        mock_get_session: MagicMock,
        mock_fetch_movements_between: MagicMock,
    ) -> None:
        fake_session = object()
        mock_get_session.return_value.__enter__.return_value = fake_session
        mock_fetch_movements_between.return_value = [object(), object()]

        payload = get_sidebar_insights_availability(reference_date=date(2026, 4, 8), user_id=55)

        self.assertTrue(payload["has_recent_records"])
        self.assertEqual(payload["recent_records_count"], 2)
        self.assertEqual(payload["window_start"], "2026-02-01")
        self.assertEqual(payload["window_end"], "2026-04-08")
        self.assertEqual(mock_fetch_movements_between.call_args.kwargs["user_id"], 55)


class AiInsightsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.allowlist_patcher = patch("punkathon_agent.cli.api.is_email_allowed", return_value=True)
        self.allowlist_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.allowlist_patcher.stop()

    @patch("punkathon_agent.cli.api.generate_goal_based_sidebar_insights")
    def test_generate_insights_endpoint_returns_payload(self, mocked_generate: unittest.mock.Mock) -> None:
        mocked_generate.return_value = {
            "generated_at": "2026-04-08T10:30:00+00:00",
            "window_start": "2026-02-01",
            "window_end": "2026-04-08",
            "has_recent_records": True,
            "recent_records_count": 12,
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
        self.assertTrue(body["has_recent_records"])
        self.assertEqual(len(body["insights"]), 1)
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertIn("user_id", mocked_generate.call_args.kwargs)

    @patch("punkathon_agent.cli.api.get_sidebar_insights_availability")
    def test_insights_status_endpoint_returns_availability(
        self,
        mocked_status: unittest.mock.Mock,
    ) -> None:
        mocked_status.return_value = {
            "has_recent_records": False,
            "recent_records_count": 0,
            "window_start": "2026-02-01",
            "window_end": "2026-04-08",
        }

        signup_response = self.client.post(
            "/auth/signup",
            json={
                "email": f"insight-status-{uuid4().hex[:8]}@example.com",
                "nome": "Iris",
                "cognome": "Status",
                "eta": 27,
                "password": "password123",
            },
        )
        token = signup_response.json()["access_token"]

        response = self.client.get(
            "/insights/status",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["has_recent_records"], False)
        self.assertEqual(mocked_status.call_count, 1)

    @patch("punkathon_agent.cli.api.generate_single_goal_based_insight", new_callable=AsyncMock)
    def test_generate_single_insight_endpoint_returns_payload(
        self,
        mocked_generate: AsyncMock,
    ) -> None:
        mocked_generate.return_value = {
            "id": "popup-1",
            "type": "warning",
            "title": "Budget che cola",
            "description": "Le uscite qui stanno andando in giro senza guinzaglio.",
            "timestamp": "2026-04-08T10:30:00+00:00",
        }

        signup_response = self.client.post(
            "/auth/signup",
            json={
                "email": f"insight-popup-{uuid4().hex[:8]}@example.com",
                "nome": "Poppy",
                "cognome": "Test",
                "eta": 24,
                "password": "password123",
            },
        )
        signup_body = signup_response.json()
        token = signup_body["access_token"]
        user_id = signup_body["user"]["id"]

        response = self.client.post(
            "/insights/generate-one",
            json={
                "type": "warning",
                "focus_hint": "Segnala il buco piu' urgente del budget",
                "existing_titles": ["Vecchio insight"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], "popup-1")
        self.assertEqual(body["type"], "warning")
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertEqual(mocked_generate.call_args.kwargs["insight_type"], "warning")
        self.assertEqual(mocked_generate.call_args.kwargs["user_id"], user_id)

    @patch("punkathon_agent.cli.api.synthesize_insight_audio")
    def test_insight_text_to_speech_endpoint_returns_mp3(
        self,
        mocked_synthesize: unittest.mock.Mock,
    ) -> None:
        mocked_synthesize.return_value = b"fake-mp3"

        signup_response = self.client.post(
            "/auth/signup",
            json={
                "email": f"insight-tts-{uuid4().hex[:8]}@example.com",
                "nome": "Audio",
                "cognome": "Test",
                "eta": 29,
                "password": "password123",
            },
        )
        token = signup_response.json()["access_token"]

        response = self.client.post(
            "/insights/text-to-speech",
            json={"text": "Budget in ordine, ma non montarti la testa."},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"fake-mp3")
        self.assertEqual(response.headers["content-type"], "audio/mpeg")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn('inline; filename="insight.mp3"', response.headers["content-disposition"])
        mocked_synthesize.assert_called_once_with("Budget in ordine, ma non montarti la testa.")


if __name__ == "__main__":
    unittest.main()
