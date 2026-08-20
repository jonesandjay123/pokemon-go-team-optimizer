import shutil
import unittest
from pathlib import Path

from pogo_team_optimizer.battle import (
    BattleMatchup,
    Moveset,
    PvPokeBridgeError,
    PvPokeEngine,
)


FIXTURES = Path(__file__).parent / "fixtures"


class PvPokeBridgeTests(unittest.TestCase):
    def test_moveset_requires_distinct_charged_moves(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct"):
            Moveset("whiscash", "MUD_SHOT", ("MUD_BOMB", "MUD_BOMB"))

    @unittest.skipUnless(shutil.which("node"), "Node.js is optional outside V3")
    def test_vendored_engine_runs_deterministic_default_build(self) -> None:
        engine = PvPokeEngine(FIXTURES / "gamemaster_battle_small.json")
        whiscash = Moveset("whiscash", "MUD_SHOT", ("BLIZZARD", "MUD_BOMB"))
        altaria = Moveset("altaria", "DRAGON_BREATH", ("SKY_ATTACK", "FLAMETHROWER"))
        results = engine.simulate([
            BattleMatchup(str(shields), whiscash, altaria, shields)
            for shields in (0, 1, 2)
        ])
        self.assertEqual([result.candidate_rating for result in results], [691, 603, 674])
        self.assertEqual([result.outcome for result in results], ["win", "win", "win"])
        self.assertEqual(results[0].candidate_build.cp, 1495)
        self.assertEqual(results[0].candidate_build.level, 27)
        self.assertEqual(
            (results[0].candidate_build.attack_iv,
             results[0].candidate_build.defense_iv,
             results[0].candidate_build.hp_iv),
            (4, 15, 15),
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js is optional outside V3")
    def test_bridge_rejects_move_outside_species_pool(self) -> None:
        engine = PvPokeEngine(FIXTURES / "gamemaster_battle_small.json")
        illegal = Moveset("whiscash", "DRAGON_BREATH", ("BLIZZARD", "MUD_BOMB"))
        altaria = Moveset("altaria", "DRAGON_BREATH", ("SKY_ATTACK", "FLAMETHROWER"))
        with self.assertRaisesRegex(PvPokeBridgeError, "not legal"):
            engine.simulate([BattleMatchup("illegal", illegal, altaria, 1)])


if __name__ == "__main__":
    unittest.main()
