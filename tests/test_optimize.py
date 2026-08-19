import contextlib
import io
import unittest

from pogo_team_optimizer.optimize import main


class OptimizeCliTests(unittest.TestCase):
    def test_cli_reports_selected_league_and_candidate_count(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main(["--league", "ultra", "--top", "75"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Ultra League (CP 2500), top 75 candidates", output.getvalue())

    def test_cli_requires_at_least_three_candidates(self) -> None:
        with self.assertRaisesRegex(SystemExit, "at least 3"):
            main(["--top", "2"])


if __name__ == "__main__":
    unittest.main()
