from __future__ import annotations

import unittest

from punkathon_agent.models.finance import serialize_classification_schema
from punkathon_agent.services.classification import _rule_based_classification


class ClassificationTests(unittest.TestCase):
    def test_classification_schema_includes_new_variable_expense_categories(self) -> None:
        schema = serialize_classification_schema()

        self.assertIn("Satispay", schema["categorie"])
        self.assertIn("Bonifici", schema["categorie"])
        self.assertIn("Prelievi", schema["categorie"])
        self.assertEqual(schema["mappa_categoria_macrocategoria"]["Satispay"], "Spese Variabili")
        self.assertEqual(schema["mappa_categoria_macrocategoria"]["Bonifici"], "Spese Variabili")
        self.assertEqual(schema["mappa_categoria_macrocategoria"]["Prelievi"], "Spese Variabili")

    def test_rule_based_classification_maps_satispay(self) -> None:
        classification = _rule_based_classification(
            {
                "descrizione": "Pagamento Satispay",
                "note": "wallet satispay negozio",
            }
        )

        self.assertIsNotNone(classification)
        self.assertEqual(classification.categoria.value, "Satispay")
        self.assertEqual(classification.macrocategoria.value, "Spese Variabili")

    def test_rule_based_classification_maps_bonifici_and_prelievi(self) -> None:
        bonifico = _rule_based_classification(
            {
                "descrizione": "Bonifico istantaneo",
                "note": "giroconti in uscita verso conto personale",
            }
        )
        prelievo = _rule_based_classification(
            {
                "descrizione": "Prelievo sportello ATM",
                "note": "prelievi bancomat",
            }
        )

        self.assertIsNotNone(bonifico)
        self.assertEqual(bonifico.categoria.value, "Bonifici")
        self.assertEqual(bonifico.macrocategoria.value, "Spese Variabili")

        self.assertIsNotNone(prelievo)
        self.assertEqual(prelievo.categoria.value, "Prelievi")
        self.assertEqual(prelievo.macrocategoria.value, "Spese Variabili")


if __name__ == "__main__":
    unittest.main()
