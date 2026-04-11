from __future__ import annotations

from contextlib import contextmanager
import json
import unittest
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from punkathon_agent.models.agent import ProfiloUtenteUpdate
from punkathon_agent.models.db import DEFAULT_USER_GOAL, PunkUser, Utente
from punkathon_agent.punkagent.request_context import reset_current_user_id, set_current_user_id
from punkathon_agent.punkagent.tools import aggiorna_profilo_utente


class ProfileToolsTests(unittest.TestCase):
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
                    email="profile-tools@example.com",
                    nome="Profile",
                    cognome="Tools",
                    eta=25,
                    password_hash="unused",
                )
            )
            session.add(
                Utente(
                    user_id=1,
                    stipendio_mensile=2000.0,
                    spese_fisse_essenziali_mensili=480.0,
                    disponibile_mensile=1400.0,
                    disponibile_settimanale=280.0,
                    obiettivo=DEFAULT_USER_GOAL,
                )
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    @contextmanager
    def _override_get_session(self):
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    @patch("punkathon_agent.punkagent.tools.create_database")
    def test_update_profile_tool_allows_fixed_expense_changes_without_altering_70_percent_budget(
        self,
        _mock_create_database: unittest.mock.Mock,
    ) -> None:
        token = set_current_user_id(1)
        try:
            with patch("punkathon_agent.punkagent.tools.get_session", new=self._override_get_session):
                response = json.loads(
                    aggiorna_profilo_utente(
                        ProfiloUtenteUpdate(spese_fisse_essenziali_mensili=650.0)
                    )
                )
        finally:
            reset_current_user_id(token)

        self.assertEqual(response["profilo"]["spese_fisse_essenziali_mensili"], 650.0)
        self.assertEqual(response["profilo"]["disponibile_mensile"], 1400.0)
        self.assertEqual(response["profilo"]["disponibile_settimanale"], 280.0)

        with Session(self.engine, expire_on_commit=False) as session:
            profile = session.exec(select(Utente).where(Utente.user_id == 1)).first()

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.spese_fisse_essenziali_mensili, 650.0)
        self.assertEqual(profile.disponibile_mensile, 1400.0)
        self.assertEqual(profile.disponibile_settimanale, 280.0)


if __name__ == "__main__":
    unittest.main()