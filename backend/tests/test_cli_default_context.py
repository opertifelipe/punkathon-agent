from __future__ import annotations

from importlib import import_module
from datetime import date
import unittest
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from punkathon_agent.cli.app import CliDefaultContext
from punkathon_agent.cli.app import app as cli_app
from punkathon_agent.models.db import DEFAULT_USER_GOAL, MovimentoBancario, PunkUser, Utente
from punkathon_agent.services.users import DEFAULT_CLI_USER_EMAIL, resolve_default_cli_user

get_command = import_module("typer.main").get_command


class DefaultCliContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        self.runner = CliRunner()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_resolve_default_cli_user_creates_user_and_profile_when_db_is_empty(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            user = resolve_default_cli_user(session)
            profile = session.exec(select(Utente).where(Utente.user_id == user.id)).first()

        self.assertIsNotNone(user.id)
        self.assertEqual(user.email, DEFAULT_CLI_USER_EMAIL)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.obiettivo, DEFAULT_USER_GOAL)

    def test_resolve_default_cli_user_claims_legacy_orphans_for_first_user(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            session.add(
                MovimentoBancario(
                    data=date(2026, 4, 11),
                    descrizione="Movimento legacy",
                    importo=-19.9,
                    note="importato prima degli utenti",
                )
            )
            session.add(Utente(obiettivo=""))
            session.commit()

            user = resolve_default_cli_user(session)
            profile = session.exec(select(Utente).where(Utente.user_id == user.id)).first()
            movement = session.exec(select(MovimentoBancario).where(MovimentoBancario.user_id == user.id)).first()

        self.assertIsNotNone(user.id)
        self.assertIsNotNone(profile)
        self.assertIsNotNone(movement)
        assert profile is not None
        self.assertEqual(profile.obiettivo, DEFAULT_USER_GOAL)

    def test_resolve_default_cli_user_reuses_existing_user(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            existing_user = PunkUser(
                email="existing@example.com",
                nome="Existing",
                cognome="User",
                eta=29,
                password_hash="not-used",
            )
            session.add(existing_user)
            session.commit()
            session.refresh(existing_user)

            resolved_user = resolve_default_cli_user(session)
            total_users = len(session.exec(select(PunkUser)).all())

        self.assertEqual(resolved_user.id, existing_user.id)
        self.assertEqual(total_users, 1)

    @patch("punkathon_agent.cli.app._stream_cli_turn", new_callable=AsyncMock)
    @patch("punkathon_agent.cli.app.get_punk_agent", return_value=object())
    @patch(
        "punkathon_agent.cli.app._resolve_default_cli_context",
        return_value=CliDefaultContext(user_id=77, frontend_context=None),
    )
    def test_chat_passes_default_cli_user_id_to_runtime(
        self,
        _mocked_context,
        _mocked_get_agent,
        mocked_stream_turn,
    ) -> None:
        mocked_stream_turn.return_value = ("ok", [])

        result = self.runner.invoke(get_command(cli_app), ["chat"], input="ciao\nexit\n")

        self.assertEqual(result.exit_code, 0)
        mocked_stream_turn.assert_awaited_once()
        self.assertEqual(mocked_stream_turn.await_args.kwargs["user_id"], 77)
        self.assertIsNone(mocked_stream_turn.await_args.kwargs["frontend_context"])


if __name__ == "__main__":
    unittest.main()