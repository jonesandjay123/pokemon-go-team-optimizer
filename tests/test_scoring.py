import unittest

from helpers import ranking_entry
from pogo_team_optimizer.scoring import DEFAULT_WEIGHTS, score_team
from pogo_team_optimizer.type_chart import PokemonType


class V1ScoringTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
