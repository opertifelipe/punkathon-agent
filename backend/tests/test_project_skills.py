from __future__ import annotations

from pathlib import Path
import unittest

from punkathon_agent.punkagent.prompts import SYSTEM_PROMPT


class ProjectSkillsTests(unittest.TestCase):
    def test_personal_finance_coach_skill_exists_with_expected_metadata(self) -> None:
        skill_path = (
            Path(__file__).resolve().parents[1]
            / "src/punkathon_agent/skills/project/personal-finance-coach/SKILL.md"
        )

        self.assertTrue(skill_path.exists(), f"Skill file mancante: {skill_path}")

        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("name: personal-finance-coach", content)
        self.assertIn("description:", content)
        self.assertIn("ottieni_profilo_utente", content)
        self.assertIn("analizza_spese_complessive", content)
        self.assertIn("calcola_spese_fisse_mensili", content)

    def test_monthly_spending_skill_mentions_semantic_current_month_tool(self) -> None:
        skill_path = (
            Path(__file__).resolve().parents[1]
            / "src/punkathon_agent/skills/project/monthly-spending-analysis/SKILL.md"
        )

        self.assertTrue(skill_path.exists(), f"Skill file mancante: {skill_path}")

        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("ottieni_movimenti_mese_corrente", content)
        self.assertIn("Do not use SQL LIKE/contains on `descrizione`", content)

    def test_budget_70_20_10_skill_exists_with_expected_guidance(self) -> None:
        skill_path = (
            Path(__file__).resolve().parents[1]
            / "src/punkathon_agent/skills/project/budget-70-20-10/SKILL.md"
        )

        self.assertTrue(skill_path.exists(), f"Skill file mancante: {skill_path}")

        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("name: budget-70-20-10", content)
        self.assertIn("70%", content)
        self.assertIn("20%", content)
        self.assertIn("10%", content)
        self.assertIn("ottieni_profilo_utente", content)
        self.assertIn("calcola_spese_fisse_mensili", content)

    def test_about_aurora_skill_exists_with_expected_guidance(self) -> None:
        skill_path = (
            Path(__file__).resolve().parents[1]
            / "src/punkathon_agent/skills/project/about-aurora/SKILL.md"
        )

        self.assertTrue(skill_path.exists(), f"Skill file mancante: {skill_path}")

        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("name: about-aurora", content)
        self.assertIn("70/20/10", content)
        self.assertIn("learning by doing", content)
        self.assertIn("chi e' Aurora?", content)

    def test_system_prompt_mentions_70_20_10_methodology(self) -> None:
        self.assertIn("70/20/10", SYSTEM_PROMPT)
        self.assertIn("70% dello stipendio", SYSTEM_PROMPT)
        self.assertIn("calcola_budget_residuo_settimana", SYSTEM_PROMPT)
        self.assertIn("3-6 mesi", SYSTEM_PROMPT)
        self.assertIn("tempo e' un grande alleato", SYSTEM_PROMPT)
        self.assertIn("saluto", SYSTEM_PROMPT)
        self.assertIn("cosa sai fare", SYSTEM_PROMPT)
        self.assertIn("presenta comunque in modo breve il 70/20/10", SYSTEM_PROMPT)
        self.assertIn("chi e' Aurora", SYSTEM_PROMPT)
        self.assertIn("modificare il valore delle spese del profilo", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
