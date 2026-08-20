import unittest
from pathlib import Path

from pogo_team_optimizer.inventory import (
    InventoryMoveState,
    inventory_candidates,
    read_inventory,
    ready_now_candidates,
)
from pogo_team_optimizer.parsing import (
    read_game_master,
    read_rankings_json,
    resolve_ranking_entries,
)
from pogo_team_optimizer.readiness import ReadinessConfig, ReadinessStatus
from pogo_team_optimizer.scout import (
    ScoutTeamClassification,
    provisional_team_classification,
    rank_move_inspection_priorities,
)
from pogo_team_optimizer.search_v2 import rank_v2_teams


FIXTURES = Path(__file__).parent / "fixtures"


class V22aScoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gm = read_game_master(
            FIXTURES / "gamemaster_small.json", FIXTURES / "aliases_small.json"
        )
        entries, species_ids = read_rankings_json(
            FIXTURES / "rankings_small.json", self.gm
        )
        self.rankings, unresolved = resolve_ranking_entries(
            entries, self.gm, species_ids
        )
        self.assertEqual(unresolved, [])
        self.inventory = read_inventory(FIXTURES / "inventory_scout.csv")

    def test_blank_moves_are_unknown_not_invalid(self) -> None:
        strict, diagnostics = inventory_candidates(
            self.inventory,
            self.rankings,
            self.gm,
            1500,
            ReadinessConfig(0.95),
        )
        diagnostic = next(
            item for item in diagnostics if item.instance_id == "unknown-grass"
        )
        self.assertEqual(diagnostic.move_state, InventoryMoveState.UNKNOWN)
        self.assertEqual(diagnostic.readiness.status, ReadinessStatus.NEEDS_MOVE_CHECK)
        self.assertNotIn(
            "unknown-grass", {candidate.instance_id for candidate in strict}
        )

    def test_invalid_named_move_remains_invalid(self) -> None:
        _, diagnostics = inventory_candidates(
            self.inventory, self.rankings, self.gm, 1500
        )
        diagnostic = next(
            item for item in diagnostics if item.instance_id == "invalid-shadow"
        )
        self.assertEqual(diagnostic.move_state, InventoryMoveState.INVALID)
        self.assertEqual(
            diagnostic.readiness.status, ReadinessStatus.INVALID_MISSING_MOVE
        )

    def test_scout_substitutes_recommended_moves_provisionally(self) -> None:
        candidates, diagnostics = inventory_candidates(
            self.inventory,
            self.rankings,
            self.gm,
            1500,
            scout_mode=True,
        )
        assumed = next(
            item for item in candidates if item.instance_id == "unknown-grass"
        )
        recommended = next(
            item for item in self.rankings if item.species_id == assumed.species_id
        )
        self.assertTrue(assumed.moves_provisional)
        self.assertEqual(assumed.moves, recommended.moves)
        diagnostic = next(
            item for item in diagnostics if item.instance_id == "unknown-grass"
        )
        self.assertEqual(diagnostic.moveset_match, "assumed-recommended")
        self.assertIsNone(diagnostic.actual_move_quality)
        self.assertIsNotNone(diagnostic.recommended_move_quality)

    def test_ready_now_rejects_unknown_moves(self) -> None:
        candidates, diagnostics = inventory_candidates(
            self.inventory,
            self.rankings,
            self.gm,
            1500,
            scout_mode=True,
        )
        ready = ready_now_candidates(candidates, diagnostics)
        self.assertTrue(all(not candidate.moves_provisional for candidate in ready))
        self.assertNotIn(
            "unknown-grass", {candidate.instance_id for candidate in ready}
        )

    def test_known_actual_moves_override_scout_assumptions(self) -> None:
        candidates, _ = inventory_candidates(
            self.inventory,
            self.rankings,
            self.gm,
            1500,
            scout_mode=True,
        )
        known = next(item for item in candidates if item.instance_id == "known-water")
        self.assertFalse(known.moves_provisional)
        self.assertEqual(known.charged_moves[0].move_id, "SURF")

    def test_priority_and_team_classification_are_deterministic(self) -> None:
        candidates, diagnostics = inventory_candidates(
            self.inventory,
            self.rankings,
            self.gm,
            1500,
            scout_mode=True,
        )
        provisional = [
            team
            for team in rank_v2_teams(candidates, scoring="v2.2")
            if any(member.moves_provisional for member in team.members)
        ]
        first = rank_move_inspection_priorities(
            candidates, provisional, self.inventory, diagnostics
        )
        second = rank_move_inspection_priorities(
            candidates, provisional, self.inventory, diagnostics
        )
        self.assertEqual(first, second)
        self.assertEqual(first[0].instance_id, "unknown-grass")
        self.assertGreaterEqual(first[0].top_team_frequency, 1)
        classifications = {
            provisional_team_classification(team.members, diagnostics)
            for team in provisional
        }
        self.assertIn(ScoutTeamClassification.NEEDS_MOVE_CHECK, classifications)
        self.assertIn(
            ScoutTeamClassification.POWER_UP_AND_MOVE_CHECK, classifications
        )


if __name__ == "__main__":
    unittest.main()
