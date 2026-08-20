import unittest
from pathlib import Path

from pogo_team_optimizer.inventory import (
    inventory_candidates,
    read_inventory,
    readiness_by_instance,
    ready_now_candidates,
    team_power_up_gaps,
)
from pogo_team_optimizer.parsing import (
    read_game_master,
    read_rankings_json,
    resolve_ranking_entries,
)
from pogo_team_optimizer.readiness import (
    ReadinessConfig,
    ReadinessStatus,
    TargetCpSource,
    assess_readiness,
)
from pogo_team_optimizer.search_v2 import rank_v2_teams


FIXTURES = Path(__file__).parent / "fixtures"


class V22ReadinessTests(unittest.TestCase):
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
        self.owned, self.diagnostics = inventory_candidates(
            read_inventory(FIXTURES / "inventory_readiness.csv"),
            self.candidates,
            self.gm,
            1500,
            ReadinessConfig(0.95),
        )
        self.assessments = readiness_by_instance(self.diagnostics)

    def test_cp_above_cap_remains_illegal(self) -> None:
        self.assertNotIn(
            "over-shadow", {candidate.instance_id for candidate in self.owned}
        )
        self.assertEqual(
            self.assessments["over-shadow"].status,
            ReadinessStatus.INELIGIBLE_OVER_CAP,
        )

    def test_low_cp_is_owned_but_power_up_needed(self) -> None:
        self.assertIn("low-fire", {candidate.instance_id for candidate in self.owned})
        assessment = self.assessments["low-fire"]
        self.assertEqual(assessment.status, ReadinessStatus.POWER_UP_NEEDED)
        self.assertEqual((assessment.target_cp, assessment.cp_gap), (1500, 600))
        self.assertEqual(
            assessment.target_source, TargetCpSource.LEAGUE_CAP_FALLBACK
        )

    def test_near_target_cp_is_ready(self) -> None:
        self.assertEqual(
            self.assessments["ready-fire"].status, ReadinessStatus.READY_NOW
        )

    def test_ready_threshold_is_configurable(self) -> None:
        self.assertEqual(
            assess_readiness(1400, 1500, 1500, ReadinessConfig(0.90)).status,
            ReadinessStatus.READY_NOW,
        )
        self.assertEqual(
            assess_readiness(1400, 1500, 1500, ReadinessConfig(0.95)).status,
            ReadinessStatus.POWER_UP_NEEDED,
        )

    def test_target_cp_from_ranking_is_preferred(self) -> None:
        assessment = assess_readiness(1140, 1200, 1500, ReadinessConfig(0.95))
        self.assertEqual(assessment.target_cp, 1200)
        self.assertEqual(assessment.target_source, TargetCpSource.RANKING)
        self.assertEqual(assessment.status, ReadinessStatus.READY_NOW)

    def test_ready_now_teams_contain_only_ready_members(self) -> None:
        ready = ready_now_candidates(self.owned, self.diagnostics)
        teams = rank_v2_teams(ready, scoring="v2.2")
        self.assertTrue(teams)
        self.assertTrue(
            all(
                self.assessments[member.instance_id].status
                is ReadinessStatus.READY_NOW
                for team in teams
                for member in team.members
            )
        )

    def test_potential_team_may_contain_power_up_member(self) -> None:
        teams = rank_v2_teams(self.owned, scoring="v2.2")
        potential = [
            team for team in teams if team_power_up_gaps(team.members, self.diagnostics)
        ]
        self.assertTrue(potential)
        self.assertTrue(
            any(
                member.instance_id == "low-fire"
                for team in potential
                for member in team.members
            )
        )

    def test_invalid_move_has_explicit_readiness_status(self) -> None:
        self.assertEqual(
            self.assessments["invalid-shadow"].status,
            ReadinessStatus.INVALID_MISSING_MOVE,
        )

    def test_v22_is_deterministic_and_keeps_v21_theoretical_scores(self) -> None:
        v21 = rank_v2_teams(self.candidates, scoring="v2.1")
        first = rank_v2_teams(self.candidates, scoring="v2.2")
        second = rank_v2_teams(self.candidates, scoring="v2.2")
        self.assertEqual(first, second)
        self.assertEqual(
            [team.score.total_score for team in first],
            [team.score.total_score for team in v21],
        )


if __name__ == "__main__":
    unittest.main()
