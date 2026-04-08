from __future__ import annotations

from importlib import import_module
import sys
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from punkathon_agent.cli.app import app as cli_app
from punkathon_agent.cli.app import main

get_command = import_module("typer.main").get_command


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_help_lists_unified_subcommands(self) -> None:
        result = self.runner.invoke(get_command(cli_app), ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("chat", result.output)
        self.assertIn("api", result.output)
        self.assertIn("rebuild-db", result.output)

    def test_api_subcommand_delegates_to_api_main(self) -> None:
        with patch("punkathon_agent.cli.api.main") as api_main:
            result = self.runner.invoke(get_command(cli_app), ["api"])

        self.assertEqual(result.exit_code, 0)
        api_main.assert_called_once_with()

    def test_main_routes_no_args_to_chat(self) -> None:
        with patch("punkathon_agent.cli.app.app") as cli_entrypoint:
            with patch.object(sys, "argv", ["punkagent"]):
                main()
                self.assertEqual(sys.argv, ["punkagent", "chat"])

        cli_entrypoint.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()