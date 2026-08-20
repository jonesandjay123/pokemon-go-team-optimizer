import unittest

from pogo_team_optimizer.battle.pvpoke import BattleBuild, BattleResult, Moveset
from pogo_team_optimizer.battle.v3 import (
    MatchupRecord,
    compare_movesets,
    summarize_moveset,
    summarize_team,
)


BUILD = BattleBuild("test", 1500, 20, 0, 15, 15, 100, 100, 100)


def record(candidate: str, opponent_rank: int, shields: int, rating: int) -> MatchupRecord:
    result = BattleResult(
        f"{candidate}|{opponent_rank}|{shields}",
        shields,
        rating,
        1000 - rating,
        "win" if rating > 500 else "loss" if rating < 500 else "tie",
        max(0, rating - 500),
        max(0, 500 - rating),
        BUILD,
        BUILD,
    )
    return MatchupRecord(
        candidate,
        opponent_rank,
        f"Opponent {opponent_rank}",
        f"opponent_{opponent_rank}",
        shields,
        result,
    )


class V3SummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = []
        # Opponent 1 is covered by two members; opponent 2 is a shared hard counter.
        for shields in (0, 1, 2):
            self.records.extend([
                record("a", 1, shields, 650),
                record("b", 1, shields, 550),
                record("c", 1, shields, 400),
                record("a", 2, shields, 450),
                record("b", 2, shields, 500),
                record("c", 2, shields, 300),
            ])

    def test_team_robustness_components_are_visible_and_deterministic(self) -> None:
        summary = summarize_team("team", ("a", "b", "c"), self.records)
        self.assertEqual(summary.meta_size, 2)
        self.assertEqual(summary.scenario_cells, 6)
        self.assertEqual(summary.covered_opponents, 3)
        self.assertEqual(summary.zero_member_wins, 3)
        self.assertEqual(summary.two_or_more_member_wins, 3)
        self.assertEqual(summary.shared_hard_counters, ("Opponent 2",))
        self.assertAlmostEqual(summary.coverage_rate, 0.5)
        self.assertAlmostEqual(summary.depth_rate, 0.5)
        self.assertAlmostEqual(summary.average_rating, 475)
        self.assertAlmostEqual(summary.robustness_score, 49.5)
        self.assertEqual(summary.worst_opponent, "Opponent 2")
        self.assertEqual(summary.worst_best_member_rating, 500)

    def test_moveset_summary_uses_rating_above_500_as_win(self) -> None:
        moveset = Moveset("test", "FAST", ("CHARGED",), "test set")
        summary = summarize_moveset("b", moveset, self.records)
        self.assertEqual((summary.wins, summary.losses, summary.ties), (3, 0, 3))
        self.assertAlmostEqual(summary.win_rate, 0.5)

    def test_comparison_reports_matchup_flips(self) -> None:
        rows = [
            record("base", 1, 0, 490),
            record("changed", 1, 0, 510),
            record("base", 2, 0, 520),
            record("changed", 2, 0, 480),
        ]
        comparison = compare_movesets("change", "base", "changed", rows)
        self.assertEqual(len(comparison.wins_gained), 1)
        self.assertEqual(len(comparison.wins_lost), 1)
        self.assertIn("Opponent 1", comparison.wins_gained[0])
        self.assertIn("Opponent 2", comparison.wins_lost[0])


if __name__ == "__main__":
    unittest.main()
