import unittest

from pogo_team_optimizer.leagues import LeagueSlug, get_league


class LeagueTests(unittest.TestCase):
    def test_great_league_has_1500_cp_cap(self) -> None:
        league = get_league("great")

        self.assertEqual(league.slug, LeagueSlug.GREAT)
        self.assertEqual(league.cp_cap, 1500)

    def test_master_league_has_no_cp_cap(self) -> None:
        self.assertIsNone(get_league("master").cp_cap)

    def test_unknown_league_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_league("little")


if __name__ == "__main__":
    unittest.main()
