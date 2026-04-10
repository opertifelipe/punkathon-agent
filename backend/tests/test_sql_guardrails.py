from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from punkathon_agent.models.agent import FiltroQuerySQL, RichiestaCostruzioneQuerySQL
from punkathon_agent.punkagent.request_context import reset_current_user_id, set_current_user_id
from punkathon_agent.punkagent.tools import costruisci_query_sql, esegui_query_sql


class SqlGuardrailTests(unittest.TestCase):
    def test_query_builder_returns_semantic_guidance_for_descrizione_contains(self) -> None:
        payload = RichiestaCostruzioneQuerySQL(
            tabella="movimenti_bancari",
            filtri=[
                FiltroQuerySQL(
                    colonna="descrizione",
                    operatore="contains",
                    valore="pizza",
                )
            ],
        )

        response = json.loads(costruisci_query_sql(payload))

        self.assertEqual(response["suggested_tool"], "ottieni_movimenti_mese_corrente")
        self.assertIn("descrizione", response["details"])

    @patch("punkathon_agent.punkagent.tools.create_database")
    def test_sql_executor_returns_semantic_guidance_for_descrizione_like(
        self,
        _mock_create_database: unittest.mock.Mock,
    ) -> None:
        token = set_current_user_id(1)
        try:
            response = json.loads(
                esegui_query_sql("SELECT * FROM movimenti_bancari WHERE descrizione LIKE '%pizza%'")
            )
        finally:
            reset_current_user_id(token)

        self.assertEqual(response["suggested_tool"], "ottieni_movimenti_mese_corrente")
        self.assertIn("alternative_tools", response)


if __name__ == "__main__":
    unittest.main()
