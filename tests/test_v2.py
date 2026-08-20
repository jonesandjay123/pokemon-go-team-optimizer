import unittest
from dataclasses import replace
from pathlib import Path

from helpers import ranking_entry
from pogo_team_optimizer.inventory import InventoryStatus, inventory_candidates, read_inventory
from pogo_team_optimizer.models import MoveKind
from pogo_team_optimizer.parsing import read_game_master, resolve_ranking_entries
from pogo_team_optimizer.scoring.v2 import coverage_summary, offensive_redundancy, score_v2_team
from pogo_team_optimizer.search_v2 import rank_v2_teams
from pogo_team_optimizer.type_chart import PokemonType


FIXTURES = Path(__file__).parent / "fixtures"


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.gm = read_game_master(FIXTURES / "gamemaster_small.json", FIXTURES / "aliases_small.json")
        entries = [
            ranking_entry(1, "妙蛙種子", PokemonType.GRASS, PokemonType.POISON, 95),
            ranking_entry(2, "小火龍", PokemonType.FIRE, score=92),
            ranking_entry(3, "傑尼龜", PokemonType.WATER, score=90),
            ranking_entry(4, "妙蛙種子 暗影", PokemonType.GRASS, PokemonType.POISON, 88),
        ]
        entries[0] = replace(entries[0], fast_move="藤鞭", charged_moves=("種子炸彈", "污泥炸彈"))
        entries[1] = replace(entries[1], fast_move="火花", charged_moves=("蓄能焰襲",))
        entries[2] = replace(entries[2], fast_move="水槍", charged_moves=("衝浪", "冰凍光束"))
        entries[3] = replace(entries[3], fast_move="藤鞭", charged_moves=("種子炸彈", "污泥炸彈"))
        self.candidates, unresolved = resolve_ranking_entries(entries, self.gm, ["bulbasaur","charmander","squirtle","bulbasaur_shadow"])
        self.assertEqual(unresolved, [])

    def test_move_parsing_kind_type_energy_and_buffs(self):
        fast = self.gm.resolve_move("藤鞭")
        charged = self.gm.resolve_move("Flame Charge")
        self.assertEqual((fast.kind, fast.move_type, fast.energy_gain), (MoveKind.FAST, PokemonType.GRASS, 8))
        self.assertEqual((charged.kind, charged.energy, charged.buffs), (MoveKind.CHARGED, 50, (1, 0)))

    def test_unresolved_moves_are_reported_not_silently_dropped(self):
        broken = replace(self.candidates[0].ranking, fast_move="不存在的招式")
        candidates, diagnostics = resolve_ranking_entries(
            [broken], self.gm, ["bulbasaur"]
        )
        self.assertEqual(candidates, [])
        self.assertIn("無法解析招式", diagnostics[0])

    def test_stab_and_single_and_dual_target_coverage(self):
        bulbasaur = self.candidates[0]
        self.assertTrue(bulbasaur.has_stab(bulbasaur.fast_move))
        summary = coverage_summary((self.gm.resolve_move("Ice Beam"),))
        self.assertIn(PokemonType.DRAGON, summary.super_effective)
        dual = coverage_summary((self.gm.resolve_move("Ice Beam"),), [(PokemonType.DRAGON, PokemonType.FLYING)])
        self.assertIn(PokemonType.DRAGON, dual.super_effective)

    def test_redundancy_and_v2_score_are_decomposed_and_deterministic(self):
        team = tuple(self.candidates[:3])
        self.assertEqual(offensive_redundancy(team), 0)
        score = score_v2_team(team)
        self.assertGreater(score.super_effective_coverage, 0)
        self.assertEqual(rank_v2_teams(self.candidates), rank_v2_teams(self.candidates))

    def test_inventory_uses_actual_moves_and_preserves_shadow_form(self):
        owned, diagnostics = inventory_candidates(read_inventory(FIXTURES / "inventory_small.csv"), self.candidates, self.gm, 1500)
        self.assertEqual(len(owned), 4)
        self.assertEqual(owned[0].charged_moves[0].move_id, "SEED_BOMB")
        self.assertEqual(len(owned[0].charged_moves), 1)
        self.assertEqual(owned[-1].species_id, "bulbasaur_shadow")
        self.assertIn(InventoryStatus.DIFFERENT_MOVES, {item.status for item in diagnostics})
        self.assertEqual(len(rank_v2_teams(owned)), 2)


if __name__ == "__main__":
    unittest.main()
