import unittest

from helpers import ranking_entry
from pogo_team_optimizer.search import candidate_team_count, rank_teams
from pogo_team_optimizer.type_chart import PokemonType


class ExhaustiveSearchTests(unittest.TestCase):
    def test_fifty_candidates_generate_19600_unordered_teams(self) -> None:
        pokemon_types = list(PokemonType)
        entries = [
            ranking_entry(
                rank=index,
                name=f"Pokemon {index:02}",
                primary_type=pokemon_types[(index - 1) % len(pokemon_types)],
                score=100 - index / 10,
            )
            for index in range(1, 51)
        ]

        results = rank_teams(entries)

        self.assertEqual(candidate_team_count(50), 19_600)
        self.assertEqual(len(results), 19_600)
        self.assertEqual(
            results,
            sorted(
                results,
                key=lambda result: (
                    -result.score.total_score,
                    tuple(member.rank for member in result.members),
                    tuple(member.name.casefold() for member in result.members),
                ),
            ),
        )

    def test_identical_inputs_have_deterministic_tie_breaking(self) -> None:
        entries = [
            ranking_entry(index, f"Pokemon {index}", PokemonType.WATER)
            for index in range(1, 6)
        ]

        first = rank_teams(entries)
        second = rank_teams(entries)

        self.assertEqual(first, second)
        self.assertEqual(tuple(member.rank for member in first[0].members), (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
