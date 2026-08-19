import csv
import json
import tempfile
import unittest
from pathlib import Path

from pogo_team_optimizer.parsing import read_rankings
from pogo_team_optimizer.scoring import ScoringName
from pogo_team_optimizer.sensitivity import (
    grouped_species_name,
    run_sensitivity_analysis,
    write_sensitivity_outputs,
)


FIXTURE = Path(__file__).parent / "fixtures" / "pvpoketw_rankings_malformed_cp.csv"


class SensitivityAnalysisTests(unittest.TestCase):
    def test_shadow_grouping_preserves_other_form_labels(self) -> None:
        self.assertEqual(grouped_species_name("七夕青鳥 暗影"), "七夕青鳥")
        self.assertEqual(grouped_species_name("太陽珊瑚 伽勒爾"), "太陽珊瑚 伽勒爾")

    def test_analysis_contains_all_models_and_stability_metrics(self) -> None:
        evaluations, summary = run_sensitivity_analysis(read_rankings(FIXTURE))

        self.assertEqual(set(evaluations), set(ScoringName))
        self.assertEqual(set(summary["models"]), {name.value for name in ScoringName})
        self.assertEqual(
            summary["stability_vs_baseline"]["baseline"]["top_10_overlap"], 10
        )
        self.assertEqual(
            summary["stability_vs_baseline"]["baseline"]["top_50_jaccard"], 1
        )

    def test_comparison_outputs_are_machine_readable(self) -> None:
        evaluations, summary = run_sensitivity_analysis(read_rankings(FIXTURE))

        with tempfile.TemporaryDirectory() as directory:
            csv_path, json_path = write_sensitivity_outputs(
                directory, evaluations, summary
            )

            with csv_path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            with json_path.open(encoding="utf-8") as file:
                loaded_summary = json.load(file)

            self.assertEqual(len(rows), len(ScoringName))
            self.assertEqual(rows[0]["scoring"], "baseline")
            self.assertEqual(loaded_summary, summary)
            for scoring_name in ScoringName:
                self.assertTrue(
                    (Path(directory) / f"top_teams_{scoring_name.value}.csv").is_file()
                )


if __name__ == "__main__":
    unittest.main()
