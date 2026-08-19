import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from pogo_team_optimizer.optimize import main


FIXTURE = Path(__file__).parent / "fixtures" / "pvpoketw_rankings_malformed_cp.csv"


class OptimizeCliTests(unittest.TestCase):
    def test_cli_reports_actionable_missing_input_error(self) -> None:
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            main(["--league", "great", "--input", "/missing/rankings.csv"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("請將 PvPoke 排名匯出檔放到這個路徑", stderr.getvalue())

    def test_cli_runs_with_fixture_and_writes_ranked_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "top_teams.csv"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--league",
                        "great",
                        "--top",
                        "6",
                        "--input",
                        str(FIXTURE),
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("evaluated 20 teams", stdout.getvalue())
            self.assertIn("Top 10:", stdout.getvalue())
            with output_path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 20)
            self.assertIn("ranking_quality", rows[0])
            self.assertIn("shared_weaknesses", rows[0])

    def test_cli_selects_experimental_scoring_variant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "combined.csv"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--league",
                        "great",
                        "--top",
                        "6",
                        "--input",
                        str(FIXTURE),
                        "--output",
                        str(output_path),
                        "--scoring",
                        "combined",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.is_file())
            self.assertIn("scoring=combined", stdout.getvalue())

    def test_cli_rejects_invalid_scoring_variant(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--scoring", "make-it-look-right"])

    def test_cli_requires_at_least_three_candidates(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--top", "2"])


if __name__ == "__main__":
    unittest.main()
