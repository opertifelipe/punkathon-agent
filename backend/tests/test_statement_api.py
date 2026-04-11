from __future__ import annotations

from datetime import date, timedelta
import unittest

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from punkathon_agent.auth import create_access_token, hash_password
from punkathon_agent.cli.api import app, get_db
from punkathon_agent.db import engine as app_engine
from punkathon_agent.models.db import DEFAULT_USER_GOAL, MovimentoBancario, PunkUser, Utente


class StatementApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine, expire_on_commit=False) as session:
            primary_user = PunkUser(
                email="alice@example.com",
                nome="Alice",
                cognome="Rossi",
                eta=24,
                password_hash=hash_password("password123"),
            )
            secondary_user = PunkUser(
                email="bob@example.com",
                nome="Bob",
                cognome="Verdi",
                eta=28,
                password_hash=hash_password("password123"),
            )
            session.add(primary_user)
            session.add(secondary_user)
            session.commit()
            session.refresh(primary_user)
            session.refresh(secondary_user)
            self.primary_user_id = primary_user.id
            self.secondary_user_id = secondary_user.id

            session.add_all(
                [
                    MovimentoBancario(
                        user_id=self.primary_user_id,
                        data=date(2026, 4, 3),
                        descrizione="Supermercato",
                        importo=-42.5,
                        note="spesa settimanale",
                        categoria="Alimentazione",
                        macrocategoria="Spese Variabili",
                    ),
                    MovimentoBancario(
                        user_id=self.primary_user_id,
                        data=date(2026, 4, 10),
                        descrizione="Affitto casa",
                        importo=-800.0,
                        note="bonifico mensile",
                        categoria="Affitto o Mutuo",
                        macrocategoria="Spese Fisse",
                    ),
                    MovimentoBancario(
                        user_id=self.primary_user_id,
                        data=date(2026, 5, 2),
                        descrizione="Bonus cliente",
                        importo=1200.0,
                        note="entrata straordinaria",
                        categoria="Entrate",
                        macrocategoria="Entrate",
                    ),
                    MovimentoBancario(
                        user_id=self.secondary_user_id,
                        data=date(2026, 4, 4),
                        descrizione="Spesa altro utente",
                        importo=-99.0,
                        note="non deve comparire",
                        categoria="Alimentazione",
                        macrocategoria="Spese Variabili",
                    ),
                ]
            )
            session.commit()

        def override_get_db():
            with Session(self.engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": f"Bearer {create_access_token(self.primary_user_id)}"}

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        app_engine.dispose()

    def test_statement_page_uses_same_five_week_windows_as_home(self) -> None:
        response = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 5},
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["filters"]["period_start"], "2026-04-29")
        self.assertEqual(body["filters"]["period_end"], "2026-05-05")
        self.assertEqual(body["filters"]["weeks"][0]["start"], "2026-04-01")
        self.assertEqual(body["filters"]["weeks"][0]["end"], "2026-04-07")
        self.assertIn("Spese Variabili", body["classification_schema"]["macrocategorie"])
        self.assertEqual(
            [item["descrizione"] for item in body["transactions"]],
            ["Bonus cliente"],
        )

    def test_user_profile_defaults_goal_and_missing_salary_to_null(self) -> None:
        response = self.client.get("/utente", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["stipendio_mensile"])
        self.assertIsNone(body["disponibile_mensile"])
        self.assertEqual(body["obiettivo"], DEFAULT_USER_GOAL)

    def test_user_profile_syncs_fixed_expenses_from_previous_complete_month(self) -> None:
        today = date.today()
        current_month_start = today.replace(day=1)
        previous_month_end = current_month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)

        with Session(self.engine, expire_on_commit=False) as session:
            session.add(
                Utente(
                    user_id=self.primary_user_id,
                    obiettivo=DEFAULT_USER_GOAL,
                    stipendio_mensile=2000.0,
                    spese_fisse_essenziali_mensili=75.33,
                )
            )
            session.add_all(
                [
                    MovimentoBancario(
                        user_id=self.primary_user_id,
                        data=previous_month_start + timedelta(days=4),
                        descrizione="Affitto sync test",
                        importo=-120.0,
                        note="bonifico mensile",
                        categoria="Affitto o Mutuo",
                        macrocategoria="Spese Fisse",
                    ),
                    MovimentoBancario(
                        user_id=self.primary_user_id,
                        data=previous_month_start + timedelta(days=8),
                        descrizione="Netflix sync test",
                        importo=-29.58,
                        note="abbonamento",
                        categoria="Abbonamenti",
                        macrocategoria="Spese Fisse",
                    ),
                    MovimentoBancario(
                        user_id=self.primary_user_id,
                        data=current_month_start,
                        descrizione="Affitto corrente sync test",
                        importo=-15.9,
                        note="parziale mese corrente",
                        categoria="Affitto o Mutuo",
                        macrocategoria="Spese Fisse",
                    ),
                ]
            )
            session.commit()

        response = self.client.get("/utente", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["spese_fisse_essenziali_mensili"], 149.58)
        self.assertEqual(body["disponibile_mensile"], 1400.0)

        with Session(self.engine, expire_on_commit=False) as session:
            profile = session.exec(select(Utente).where(Utente.user_id == self.primary_user_id)).first()

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.spese_fisse_essenziali_mensili, 149.58)
        self.assertEqual(profile.disponibile_mensile, 1400.0)

    def test_patch_utente_uses_70_percent_of_salary_for_available_budget(self) -> None:
        response = self.client.patch(
            "/utente",
            json={"stipendio_mensile": 2500.0},
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stipendio_mensile"], 2500.0)
        self.assertEqual(body["disponibile_mensile"], 1750.0)

    def test_statement_transaction_crud_roundtrip(self) -> None:
        create_response = self.client.post(
            "/estratto-conto/movimenti",
            json={
                "data": "2026-04-04",
                "descrizione": "Bar sotto casa",
                "note": "colazione",
                "importo": -6.5,
                "macrocategoria": "Spese Variabili",
                "categoria": "Bar",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        movement_id = created["id"]
        self.assertEqual(created["categoria"], "Bar")

        update_response = self.client.put(
            f"/estratto-conto/movimenti/{movement_id}",
            json={
                "data": "2026-04-05",
                "descrizione": "Rimborso ristorante",
                "note": "storno su carta",
                "importo": 18.4,
                "macrocategoria": "Entrate",
                "categoria": "Entrate",
            },
            headers=self.auth_headers,
        )

        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["descrizione"], "Rimborso ristorante")
        self.assertEqual(updated["data"], "2026-04-05")
        self.assertEqual(updated["categoria"], "Entrate")
        self.assertEqual(updated["macrocategoria"], "Entrate")

        week_response = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 1},
            headers=self.auth_headers,
        )
        self.assertEqual(week_response.status_code, 200)
        week_body = week_response.json()
        descriptions = [item["descrizione"] for item in week_body["transactions"]]
        self.assertIn("Rimborso ristorante", descriptions)
        self.assertNotIn("Bar sotto casa", descriptions)

        delete_response = self.client.delete(
            f"/estratto-conto/movimenti/{updated['id']}",
            headers=self.auth_headers,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["deleted"])

        final_response = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 1},
            headers=self.auth_headers,
        )
        self.assertEqual(final_response.status_code, 200)
        final_descriptions = [item["descrizione"] for item in final_response.json()["transactions"]]
        self.assertNotIn("Rimborso ristorante", final_descriptions)

    def test_delete_all_transactions_only_removes_authenticated_user_data(self) -> None:
        delete_response = self.client.delete(
            "/estratto-conto/movimenti",
            headers=self.auth_headers,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["deleted"])
        self.assertEqual(delete_response.json()["deleted_count"], 3)

        remaining_primary = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 1},
            headers=self.auth_headers,
        )
        self.assertEqual(remaining_primary.status_code, 200)
        self.assertEqual(remaining_primary.json()["transactions"], [])

        other_user_headers = {"Authorization": f"Bearer {create_access_token(self.secondary_user_id)}"}
        remaining_secondary = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 1},
            headers=other_user_headers,
        )
        self.assertEqual(remaining_secondary.status_code, 200)
        self.assertEqual(
            [item["descrizione"] for item in remaining_secondary.json()["transactions"]],
            ["Spesa altro utente"],
        )

    def test_statement_page_is_scoped_to_authenticated_user(self) -> None:
        response = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 1},
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        descriptions = [item["descrizione"] for item in response.json()["transactions"]]
        self.assertIn("Supermercato", descriptions)
        self.assertNotIn("Spesa altro utente", descriptions)

    def test_auth_me_returns_authenticated_user(self) -> None:
        response = self.client.get("/auth/me", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["email"], "alice@example.com")
        self.assertEqual(body["nome"], "Alice")


if __name__ == "__main__":
    unittest.main()
