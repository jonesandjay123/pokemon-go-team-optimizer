import unittest
from pathlib import Path

from helpers import ranking_entry
from pogo_team_optimizer.parsing import read_rankings
from pogo_team_optimizer.scoring import (
    BASELINE_CONFIG,
    COMBINED_CONFIG,
    DEFAULT_WEIGHTS,
    DIMINISHING_RESISTANCE_CONFIG,
    EXPOSURE_AWARE_CONFIG,
    SCORING_CONFIGS,
    SEVERE_PENALTY_CONFIG,
    ResistanceCoverageStrategy,
    exposure_aware_type_coverage,
    score_team,
    transform_resistance_coverage,
)
from pogo_team_optimizer.search import rank_teams
from pogo_team_optimizer.type_chart import PokemonType


FIXTURE = Path(__file__).parent / "fixtures" / "pvpoketw_rankings_malformed_cp.csv"


class V1ScoringTests(unittest.TestCase):
    def test_baseline_fixture_result_is_backward_compatible(self) -> None:
        result = rank_teams(read_rankings(FIXTURE), scoring_config=BASELINE_CONFIG)[0]

        self.assertEqual(
            tuple(member.name for member in result.members),
            ("大舌舔", "巨鍛匠", "七夕青鳥"),
        )
        self.assertAlmostEqual(result.score.total_score, 89.12333333333333)

    def test_score_is_decomposed_and_matches_documented_formula(self) -> None:
        team = (
            ranking_entry(1, "Water", PokemonType.WATER, score=95),
            ranking_entry(2, "Grass", PokemonType.GRASS, score=90),
            ranking_entry(3, "Fire", PokemonType.FIRE, score=85),
        )

        result = score_team(team)

        components = (
            result.ranking_quality,
            result.shared_weakness_penalty,
            result.severe_weakness_penalty,
            result.resistance_coverage,
            result.teammate_weakness_coverage,
            result.defensive_diversity,
        )
        self.assertTrue(all(0 <= component <= 1 for component in components))
        expected = (
            DEFAULT_WEIGHTS.ranking_quality * result.ranking_quality
            + DEFAULT_WEIGHTS.resistance_coverage * result.resistance_coverage
            + DEFAULT_WEIGHTS.teammate_weakness_coverage
            * result.teammate_weakness_coverage
            + DEFAULT_WEIGHTS.defensive_diversity * result.defensive_diversity
            - DEFAULT_WEIGHTS.shared_weakness_penalty
            * result.shared_weakness_penalty
            - DEFAULT_WEIGHTS.severe_weakness_penalty
            * result.severe_weakness_penalty
        )
        self.assertAlmostEqual(result.total_score, expected)

    def test_three_members_with_same_weakness_receive_shared_penalty(self) -> None:
        team = tuple(
            ranking_entry(index, f"Normal {index}", PokemonType.NORMAL)
            for index in range(1, 4)
        )

        result = score_team(team)

        self.assertGreater(result.shared_weakness_penalty, 0)
        self.assertGreater(result.severe_weakness_penalty, 0)

    def test_diminishing_resistance_is_monotonic_with_smaller_late_gains(self) -> None:
        values = [
            transform_resistance_coverage(
                count / 18, ResistanceCoverageStrategy.DIMINISHING, 0.5
            )
            for count in range(19)
        ]

        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], 0)
        self.assertEqual(values[-1], 1)
        self.assertGreater(values[1] - values[0], values[-1] - values[-2])

    def test_exposure_aware_examples_distinguish_supply_and_demand(self) -> None:
        self.assertEqual(exposure_aware_type_coverage(1, 1), 0.75)
        self.assertEqual(exposure_aware_type_coverage(2, 1), 0.5)
        self.assertEqual(exposure_aware_type_coverage(1, 2), 1.0)
        self.assertEqual(exposure_aware_type_coverage(2, 0), 0.0)

    def test_each_variant_changes_only_its_documented_strategy(self) -> None:
        self.assertEqual(
            DIMINISHING_RESISTANCE_CONFIG.teammate_strategy,
            BASELINE_CONFIG.teammate_strategy,
        )
        self.assertNotEqual(
            DIMINISHING_RESISTANCE_CONFIG.resistance_strategy,
            BASELINE_CONFIG.resistance_strategy,
        )
        self.assertEqual(
            EXPOSURE_AWARE_CONFIG.resistance_strategy,
            BASELINE_CONFIG.resistance_strategy,
        )
        self.assertNotEqual(
            EXPOSURE_AWARE_CONFIG.teammate_strategy,
            BASELINE_CONFIG.teammate_strategy,
        )
        self.assertEqual(
            COMBINED_CONFIG.resistance_strategy,
            DIMINISHING_RESISTANCE_CONFIG.resistance_strategy,
        )
        self.assertEqual(
            COMBINED_CONFIG.teammate_strategy,
            EXPOSURE_AWARE_CONFIG.teammate_strategy,
        )
        self.assertEqual(
            SEVERE_PENALTY_CONFIG.weights.severe_weakness_penalty,
            DEFAULT_WEIGHTS.severe_weakness_penalty * 3,
        )

    def test_every_variant_is_deterministic(self) -> None:
        entries = read_rankings(FIXTURE)

        for config in SCORING_CONFIGS.values():
            with self.subTest(scoring=config.name.value):
                self.assertEqual(
                    rank_teams(entries, scoring_config=config),
                    rank_teams(entries, scoring_config=config),
                )


if __name__ == "__main__":
    unittest.main()
