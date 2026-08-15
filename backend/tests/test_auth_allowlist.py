from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from punkathon_agent.auth import ALLOWED_EMAILS_ENV_VAR, AUTH_SECRET_ENV_VAR, is_email_allowed
from punkathon_agent.cli.api import app, get_db
from punkathon_agent.db import engine as app_engine


class AuthAllowlistTests(unittest.TestCase):
    def test_email_allowlist_rejects_when_env_is_empty(self) -> None:
        with patch.dict(os.environ, {ALLOWED_EMAILS_ENV_VAR: ""}):
            self.assertFalse(is_email_allowed("anyone@example.com"))

    def test_email_allowlist_accepts_only_configured_addresses(self) -> None:
        with patch.dict(
            os.environ,
            {ALLOWED_EMAILS_ENV_VAR: "owner@example.com, Alice@Example.com"},
        ):
            self.assertTrue(is_email_allowed("OWNER@EXAMPLE.COM"))
            self.assertTrue(is_email_allowed("alice@example.com"))
            self.assertFalse(is_email_allowed("bob@example.com"))

    def test_signup_rejects_email_outside_allowlist(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)

        def override_get_db():
            with Session(engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        try:
            with patch.dict(
                os.environ,
                {
                    ALLOWED_EMAILS_ENV_VAR: "owner@example.com",
                    AUTH_SECRET_ENV_VAR: "test-auth-secret-32-bytes-minimum",
                },
            ):
                response = client.post(
                    "/auth/signup",
                    json={
                        "email": "someone@example.com",
                        "nome": "Mario",
                        "cognome": "Rossi",
                        "eta": 30,
                        "password": "password123",
                    },
                )

            self.assertEqual(response.status_code, 403)
        finally:
            client.close()
            app.dependency_overrides.clear()
            engine.dispose()
            app_engine.dispose()


if __name__ == "__main__":
    unittest.main()
