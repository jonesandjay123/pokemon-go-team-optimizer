"""League definitions shared by every optimization stage."""

from dataclasses import dataclass
from enum import StrEnum


class LeagueSlug(StrEnum):
    GREAT = "great"
    ULTRA = "ultra"
    MASTER = "master"


@dataclass(frozen=True, slots=True)
class League:
    slug: LeagueSlug
    display_name: str
    cp_cap: int | None

    @property
    def directory_name(self) -> str:
        return f"{self.slug.value}_league"

    @property
    def ranking_filename(self) -> str:
        cp_value = self.cp_cap if self.cp_cap is not None else 10000
        return f"cp{cp_value}_all_overall_rankings.csv"


LEAGUES: dict[LeagueSlug, League] = {
    LeagueSlug.GREAT: League(LeagueSlug.GREAT, "Great League", 1500),
    LeagueSlug.ULTRA: League(LeagueSlug.ULTRA, "Ultra League", 2500),
    LeagueSlug.MASTER: League(LeagueSlug.MASTER, "Master League", None),
}


def get_league(slug: str) -> League:
    """Return a league definition from its CLI slug."""
    return LEAGUES[LeagueSlug(slug)]
