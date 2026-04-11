from __future__ import annotations

import unittest
from datetime import date

from punkathon_agent.models.db import MovimentoBancario, Utente
from punkathon_agent.models.finance import CategoriaSpesa, MacroCategoriaSpesa
from punkathon_agent.services.spending import (
    build_fixed_expense_context,
    build_fixed_expense_monthly_summary,
    build_fixed_expense_scope_payload,
)


class FixedExpenseReasoningTests(unittest.TestCase):
    def test_macrocategory_fixed_summary_includes_subscriptions(self) -> None:
        movements = [
            MovimentoBancario(
                data=date(2026, 1, 5),
                descrizione="Affitto casa",
                importo=-900.0,
                categoria=CategoriaSpesa.AFFITTO_O_MUTUO.value,
                macrocategoria=MacroCategoriaSpesa.SPESE_FISSE.value,
            ),
            MovimentoBancario(
                data=date(2026, 1, 15),
                descrizione="Figma",
                importo=-20.0,
                categoria=CategoriaSpesa.ABBONAMENTI.value,
                macrocategoria=MacroCategoriaSpesa.SPESE_FISSE.value,
            ),
            MovimentoBancario(
                data=date(2026, 1, 20),
                descrizione="Supermercato",
                importo=-80.0,
                categoria=CategoriaSpesa.ALIMENTAZIONE.value,
                macrocategoria=MacroCategoriaSpesa.SPESE_VARIABILI.value,
            ),
            MovimentoBancario(
                data=date(2026, 2, 5),
                descrizione="Affitto casa",
                importo=-1000.0,
                categoria=CategoriaSpesa.AFFITTO_O_MUTUO.value,
                macrocategoria=MacroCategoriaSpesa.SPESE_FISSE.value,
            ),
            MovimentoBancario(
                data=date(2026, 2, 15),
                descrizione="Figma",
                importo=-24.4,
                categoria=CategoriaSpesa.ABBONAMENTI.value,
                macrocategoria=MacroCategoriaSpesa.SPESE_FISSE.value,
            ),
        ]

        summary = build_fixed_expense_monthly_summary(
            movements,
            reference_date=date(2026, 3, 10),
            preview_limit=10,
        )

        self.assertEqual(summary["mese_riferimento"], "2026-02")
        self.assertAlmostEqual(summary["spese_fisse_mensili_stimate"], 1024.4)
        categories = {row["categoria"] for row in summary["dettaglio_voci"]}
        self.assertIn(CategoriaSpesa.ABBONAMENTI.value, categories)
        self.assertNotIn(CategoriaSpesa.ALIMENTAZIONE.value, categories)

    def test_fixed_expense_context_separates_macrocategory_from_profile(self) -> None:
        profile = Utente(
            user_id=1,
            spese_fisse_essenziali_mensili=265.33,
        )

        context = build_fixed_expense_context(
            profile=profile,
            fixed_expenses_status="presenti",
            fixed_expenses_evidence=[{"descrizione": "Affitto casa", "importo_mensile": 190.0}],
            preview_limit=5,
        )

        self.assertEqual(context["richiesta_generica_utente"]["usa"], "spese_fisse_da_macrocategoria")
        self.assertIn("monitoraggio", context["profilo_utente"]["usa_per"])
        self.assertIn("70% dello stipendio", context["nota"])
        self.assertFalse(context["confronto_automatico_consigliato"])

    def test_fixed_expense_scope_payload_can_expose_compact_macro_summary(self) -> None:
        profile = Utente(
            user_id=1,
            spese_fisse_essenziali_mensili=265.33,
        )
        fixed_summary = {
            "mesi_completi_disponibili": ["2026-01", "2026-02"],
            "spese_fisse_mensili_stimate": 329.68,
            "spese_fisse_mese_corrente": 329.68,
            "dettaglio_voci": [],
        }

        payload = build_fixed_expense_scope_payload(
            profile=profile,
            fixed_expenses_status="presenti",
            fixed_expenses_evidence=[],
            preview_limit=3,
            fixed_expense_summary=fixed_summary,
            include_full_macro_summary=False,
        )

        self.assertEqual(payload["spese_fisse_da_macrocategoria"]["spese_fisse_mensili_stimate"], 329.68)
        self.assertEqual(payload["spese_fisse_da_macrocategoria"]["mesi_completi_disponibili_count"], 2)


if __name__ == "__main__":
    unittest.main()
