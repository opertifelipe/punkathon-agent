from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import json
import unittest
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from punkathon_agent.models.agent import RichiestaAnalisiSettimana
from punkathon_agent.models.db import MovimentoBancario, PunkUser, Utente
from punkathon_agent.punkagent.request_context import reset_current_user_id, set_current_user_id
from punkathon_agent.punkagent.tools import calcola_budget_residuo_settimana


class WeeklyBudgetToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine, expire_on_commit=False) as session:
            session.add(
                PunkUser(
                    id=1,
                    email="weekly-budget@example.com",
                    nome="Weekly",
                    cognome="Budget",
                    eta=26,
                    password_hash="unused",
                )
            )
            session.add(
                Utente(
                    user_id=1,
                    stipendio_mensile=2500.0,
                    spese_fisse_essenziali_mensili=920.0,
                    disponibile_mensile=1750.0,
                    disponibile_settimanale=350.0,
                )
            )
            session.add_all(
                [
                    MovimentoBancario(
                        user_id=1,
                        data=date(2026, 4, 8),
                        descrizione="Supermercato",
                        importo=-90.0,
                        categoria="Alimentazione",
                        macrocategoria="Spese Variabili",
                    ),
                    MovimentoBancario(
                        user_id=1,
                        data=date(2026, 4, 10),
                        descrizione="Affitto settimana test",
                        importo=-60.0,
                        categoria="Affitto o Mutuo",
                        macrocategoria="Spese Fisse",
                    ),
                ]
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    @contextmanager
    def _override_get_session(self):
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    @patch("punkathon_agent.punkagent.tools.create_database")
    def test_weekly_residual_budget_uses_actual_weekly_spending_not_profile_fixed_expenses(
        self,
        _mock_create_database: unittest.mock.Mock,
    ) -> None:
        token = set_current_user_id(1)
        try:
            with patch("punkathon_agent.punkagent.tools.get_session", new=self._override_get_session):
                payload = json.loads(
                    calcola_budget_residuo_settimana(
                        RichiestaAnalisiSettimana(
                            data_da=date(2026, 4, 7),
                            data_a=date(2026, 4, 13),
                            label_periodo="Settimana 2",
                            preview_limit=3,
                        )
                    )
                )
        finally:
            reset_current_user_id(token)

        self.assertEqual(payload["budget_settimanale"], 350.0)
        self.assertEqual(payload["spese_gia_fatte"], 150.0)
        self.assertEqual(payload["residuo_budget"], 200.0)
        self.assertEqual(payload["periodo"]["label"], "Settimana 2")
        self.assertNotIn("spese_fisse_essenziali_mensili", payload)


if __name__ == "__main__":
    unittest.main()