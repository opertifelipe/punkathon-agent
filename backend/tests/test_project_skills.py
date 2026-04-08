from __future__ import annotations

from pathlib import Path
import unittest


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


if __name__ == "__main__":
    unittest.main()
