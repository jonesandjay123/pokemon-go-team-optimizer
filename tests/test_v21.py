import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pogo_team_optimizer.inventory import inventory_candidates, read_inventory
from pogo_team_optimizer.inventory_template import write_template
from pogo_team_optimizer.parsing import (
    read_game_master,
    read_rankings_json,
    resolve_ranking_entries,
)
from pogo_team_optimizer.scoring.v21 import candidate_move_quality
from pogo_team_optimizer.search_v2 import is_legal_team, rank_v2_teams


FIXTURES = Path(__file__).parent / "fixtures"


class V21CorrectnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gm = read_game_master(
            FIXTURES / "gamemaster_small.json", FIXTURES / "aliases_small.json"
        )
        entries, species_ids = read_rankings_json(
            FIXTURES / "rankings_small.json", self.gm
        )
        self.candidates, unresolved = resolve_ranking_entries(
            entries, self.gm, species_ids
        )
        self.assertEqual(unresolved, [])

    def test_two_instances_of_same_species_are_illegal(self) -> None:
        first = replace(self.candidates[0], instance_id="one")
        second = replace(self.candidates[0], instance_id="two")
        self.assertFalse(is_legal_team((first, second, self.candidates[1])))
        results = rank_v2_teams(
            (first, second, self.candidates[1], self.candidates[2]),
            scoring="v2.1",
        )
        self.assertTrue(
            all(
                len({member.team_species_key for member in result.members}) == 3
                for result in results
            )
        )

    def test_normal_and_shadow_same_species_are_illegal(self) -> None:
        self.assertFalse(
            is_legal_team(
                (self.candidates[0], self.candidates[3], self.candidates[1])
            )
        )

    def test_three_different_species_are_legal(self) -> None:
        self.assertTrue(is_legal_team(tuple(self.candidates[:3])))

    def test_poor_actual_move_changes_quality_with_same_type_coverage(self) -> None:
        squirtle = self.candidates[2]
        poor_water_move = self.gm.resolve_move("Water Pulse")
        actual = replace(
            squirtle,
            charged_moves=(poor_water_move, squirtle.charged_moves[1]),
        )
        quality = candidate_move_quality(actual)
        self.assertEqual(
            actual.charged_moves[0].move_type,
            squirtle.charged_moves[0].move_type,
        )
        self.assertLess(quality.actual.total_score, quality.recommended.total_score)
        self.assertLess(quality.delta, 0)

    def test_one_charged_move_is_valid_and_diagnosed(self) -> None:
        owned, diagnostics = inventory_candidates(
            read_inventory(FIXTURES / "inventory_small.csv"),
            self.candidates,
            self.gm,
            1500,
        )
        grass = next(item for item in owned if item.instance_id == "owned-grass")
        diagnostic = next(
            item for item in diagnostics if item.instance_id == "owned-grass"
        )
        self.assertEqual(len(grass.charged_moves), 1)
        self.assertTrue(diagnostic.second_charged_move_missing)
        self.assertEqual(diagnostic.moveset_match, "partial")
        self.assertLess(diagnostic.move_quality_delta, 0)
        self.assertEqual(diagnostic.actual_moves[0], "Vine Whip")
        self.assertEqual(diagnostic.recommended_moves[0], "Vine Whip")
        water_diagnostic = next(
            item for item in diagnostics if item.instance_id == "owned-water"
        )
        self.assertEqual(water_diagnostic.moveset_match, "exact")

    def test_actual_moves_replace_but_retain_recommended_moves(self) -> None:
        owned, _ = inventory_candidates(
            read_inventory(FIXTURES / "inventory_small.csv"),
            self.candidates,
            self.gm,
            1500,
        )
        water = next(item for item in owned if item.instance_id == "owned-water")
        self.assertEqual(water.charged_moves[0].move_id, "ICE_BEAM")
        self.assertEqual(water.recommended_charged_moves[0].move_id, "SURF")

    def test_inventory_intersection_searches_beyond_top_50(self) -> None:
        fake_prefix = [
            replace(
                self.candidates[0],
                ranking=replace(self.candidates[0].ranking, rank=index),
                species_id=f"fake_{index}",
                team_species_key=f"dex:fake_{index}",
            )
            for index in range(1, 51)
        ]
        deep = [
            replace(candidate, ranking=replace(candidate.ranking, rank=rank))
            for rank, candidate in zip((51, 52, 53, 54), self.candidates)
        ]
        owned, _ = inventory_candidates(
            read_inventory(FIXTURES / "inventory_small.csv"),
            [*fake_prefix, *deep],
            self.gm,
            1500,
        )
        self.assertEqual(min(candidate.rank for candidate in owned), 51)
        self.assertTrue(rank_v2_teams(owned, scoring="v2.1"))

    def test_v21_is_deterministic(self) -> None:
        first = rank_v2_teams(self.candidates, scoring="v2.1")
        second = rank_v2_teams(self.candidates, scoring="v2.1")
        self.assertEqual(first, second)

    def test_inventory_template_is_safe_and_has_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "great_league.csv"
            write_template(path)
            text = path.read_text(encoding="utf-8-sig")
            self.assertIn("instance_id,pokemon_name", text)
            self.assertIn("未解鎖可留白", text)
            with self.assertRaises(FileExistsError):
                write_template(path)


if __name__ == "__main__":
    unittest.main()
