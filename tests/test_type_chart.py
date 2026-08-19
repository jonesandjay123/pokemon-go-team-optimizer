import unittest

from pogo_team_optimizer.type_chart import (
    IMMUNE,
    RESISTED,
    SUPER_EFFECTIVE,
    PokemonType,
    effectiveness,
)


class TypeEffectivenessTests(unittest.TestCase):
    def test_single_type_weakness_and_resistance(self) -> None:
        self.assertEqual(
            effectiveness(PokemonType.FIRE, (PokemonType.GRASS,)), SUPER_EFFECTIVE
        )
        self.assertEqual(
            effectiveness(PokemonType.FIRE, (PokemonType.WATER,)), RESISTED
        )

    def test_pokemon_go_immunity_multiplier(self) -> None:
        self.assertEqual(
            effectiveness(PokemonType.GHOST, (PokemonType.NORMAL,)), IMMUNE
        )

    def test_dual_weakness_stacks(self) -> None:
        self.assertAlmostEqual(
            effectiveness(
                PokemonType.ICE, (PokemonType.DRAGON, PokemonType.FLYING)
            ),
            SUPER_EFFECTIVE**2,
        )

    def test_weakness_and_immunity_stack_to_resistance(self) -> None:
        self.assertAlmostEqual(
            effectiveness(
                PokemonType.ELECTRIC, (PokemonType.WATER, PokemonType.GROUND)
            ),
            RESISTED,
        )

    def test_all_eighteen_attacking_types_are_supported(self) -> None:
        for attacking_type in PokemonType:
            self.assertGreater(effectiveness(attacking_type, (PokemonType.STEEL,)), 0)


if __name__ == "__main__":
    unittest.main()
