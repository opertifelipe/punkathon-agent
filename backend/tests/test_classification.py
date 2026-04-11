from __future__ import annotations

import unittest
from unittest.mock import patch

from punkathon_agent.models.finance import (
    BatchClassificazioneMovimenti,
    CategoriaSpesa,
    ClassificazioneMovimentoIndicizzata,
    MacroCategoriaSpesa,
    serialize_classification_schema,
)
from punkathon_agent.services.classification import _rule_based_classification, classifica_movimenti


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

    @patch("punkathon_agent.services.classification._invoke_batch_classification")
    def test_classifica_movimenti_falls_back_when_batch_ai_classification_fails(
        self,
        mocked_invoke_batch_classification: unittest.mock.Mock,
    ) -> None:
        mocked_invoke_batch_classification.side_effect = RuntimeError("provider output invalid")

        classifications = classifica_movimenti(
            [
                {
                    "descrizione": "Pagamento sconosciuto 1",
                    "note": None,
                    "importo": -12.5,
                },
                {
                    "descrizione": "Pagamento sconosciuto 2",
                    "note": None,
                    "importo": -7.0,
                },
            ]
        )

        self.assertEqual(len(classifications), 2)
        self.assertTrue(
            all(classification.categoria.value == "Altro Non Essenziale" for classification in classifications)
        )
        self.assertTrue(
            all(classification.macrocategoria.value == "Spese Variabili" for classification in classifications)
        )

    @patch("punkathon_agent.services.classification._invoke_batch_classification")
    def test_classifica_movimenti_retries_batch_before_fallback(
        self,
        mocked_invoke_batch_classification: unittest.mock.Mock,
    ) -> None:
        mocked_invoke_batch_classification.side_effect = [
            RuntimeError("temporary provider error"),
            RuntimeError("temporary provider error"),
            BatchClassificazioneMovimenti(
                classificazioni=[
                    ClassificazioneMovimentoIndicizzata(
                        indice=0,
                        categoria=CategoriaSpesa.ALTRO_NON_ESSENZIALE,
                        macrocategoria=MacroCategoriaSpesa.SPESE_VARIABILI,
                    ),
                    ClassificazioneMovimentoIndicizzata(
                        indice=1,
                        categoria=CategoriaSpesa.ALTRO_NON_ESSENZIALE,
                        macrocategoria=MacroCategoriaSpesa.SPESE_VARIABILI,
                    ),
                ]
            ),
        ]

        classifications = classifica_movimenti(
            [
                {
                    "descrizione": "Pagamento sconosciuto retry 1",
                    "note": None,
                    "importo": -12.5,
                },
                {
                    "descrizione": "Pagamento sconosciuto retry 2",
                    "note": None,
                    "importo": -7.0,
                },
            ]
        )

        self.assertEqual(len(classifications), 2)
        self.assertEqual(mocked_invoke_batch_classification.call_count, 3)


if __name__ == "__main__":
    unittest.main()
