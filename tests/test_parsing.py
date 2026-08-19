import csv
import unittest
from pathlib import Path

from pogo_team_optimizer.parsing import read_rankings, repair_malformed_header, select_top
from pogo_team_optimizer.type_chart import PokemonType


FIXTURE = Path(__file__).parent / "fixtures" / "pvpoketw_rankings_malformed_cp.csv"


class PvPokeCsvTests(unittest.TestCase):
    def test_known_pvpoketw_header_defect_is_repaired_after_level(self) -> None:
        with FIXTURE.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))

        repaired, was_repaired = repair_malformed_header(rows[0], rows[1:])

        self.assertTrue(was_repaired)
        level_index = repaired.index("等級")
        self.assertEqual(repaired[level_index + 1], "CP")
        self.assertEqual(len(repaired), len(rows[1]))

    def test_rows_are_normalized_without_column_shifting(self) -> None:
        entries = read_rankings(FIXTURE)

        self.assertEqual(len(entries), 6)
        self.assertEqual(entries[0].rank, 1)
        self.assertEqual(entries[0].name, "大舌舔")
        self.assertEqual(entries[0].primary_type, PokemonType.NORMAL)
        self.assertIsNone(entries[0].secondary_type)
        self.assertEqual(entries[0].level, 23)
        self.assertEqual(entries[0].cp, 1499)
        self.assertEqual(entries[0].fast_move, "滾動")
        self.assertEqual(entries[0].charged_moves, ("泰山壓頂", "暗影球"))
        self.assertEqual(entries[1].secondary_type, PokemonType.STEEL)

    def test_top_n_selection_preserves_ranking_order(self) -> None:
        selected = select_top(read_rankings(FIXTURE), 3)

        self.assertEqual([entry.rank for entry in selected], [1, 2, 3])
        self.assertEqual(
            [entry.name for entry in selected], ["大舌舔", "巨鍛匠", "七夕青鳥"]
        )


if __name__ == "__main__":
    unittest.main()
