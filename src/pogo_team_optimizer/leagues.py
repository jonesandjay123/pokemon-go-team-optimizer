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


LEAGUES: dict[LeagueSlug, League] = {
    LeagueSlug.GREAT: League(LeagueSlug.GREAT, "Great League", 1500),
    LeagueSlug.ULTRA: League(LeagueSlug.ULTRA, "Ultra League", 2500),
    LeagueSlug.MASTER: League(LeagueSlug.MASTER, "Master League", None),
}


def get_league(slug: str) -> League:
    """Return a league definition from its CLI slug."""
    return LEAGUES[LeagueSlug(slug)]
