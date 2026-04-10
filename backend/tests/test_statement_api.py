from __future__ import annotations

from datetime import date
import unittest

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from punkathon_agent.cli.api import app, get_db
from punkathon_agent.db import engine as app_engine
from punkathon_agent.models.db import DEFAULT_USER_GOAL, MovimentoBancario


class StatementApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    MovimentoBancario(
                        data=date(2026, 4, 3),
                        descrizione="Supermercato",
                        importo=-42.5,
                        note="spesa settimanale",
                        categoria="Alimentazione",
                        macrocategoria="Spese Variabili",
                    ),
                    MovimentoBancario(
                        data=date(2026, 4, 10),
                        descrizione="Affitto casa",
                        importo=-800.0,
                        note="bonifico mensile",
                        categoria="Affitto o Mutuo",
                        macrocategoria="Spese Fisse",
                    ),
                    MovimentoBancario(
                        data=date(2026, 5, 2),
                        descrizione="Bonus cliente",
                        importo=1200.0,
                        note="entrata straordinaria",
                        categoria="Entrate",
                        macrocategoria="Entrate",
                    ),
                ]
            )
            session.commit()

        def override_get_db():
            with Session(self.engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        app_engine.dispose()

    def test_statement_page_uses_same_five_week_windows_as_home(self) -> None:
        response = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 5},
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
        response = self.client.get("/utente")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["stipendio_mensile"])
        self.assertIsNone(body["disponibile_mensile"])
        self.assertEqual(body["obiettivo"], DEFAULT_USER_GOAL)

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
        )
        self.assertEqual(week_response.status_code, 200)
        week_body = week_response.json()
        descriptions = [item["descrizione"] for item in week_body["transactions"]]
        self.assertIn("Rimborso ristorante", descriptions)
        self.assertNotIn("Bar sotto casa", descriptions)

        delete_response = self.client.delete(f"/estratto-conto/movimenti/{updated['id']}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["deleted"])

        final_response = self.client.get(
            "/estratto-conto",
            params={"year": 2026, "month": 4, "week": 1},
        )
        self.assertEqual(final_response.status_code, 200)
        final_descriptions = [item["descrizione"] for item in final_response.json()["transactions"]]
        self.assertNotIn("Rimborso ristorante", final_descriptions)


if __name__ == "__main__":
    unittest.main()
