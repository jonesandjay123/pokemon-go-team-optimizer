"""Normalized domain models used after data ingestion."""

from dataclasses import dataclass

from pogo_team_optimizer.type_chart import PokemonType


@dataclass(frozen=True, slots=True)
class RankingEntry:
    """One ranking row in the canonical, source-independent format."""

    rank: int
    name: str
    score: float
    primary_type: PokemonType
    secondary_type: PokemonType | None
    attack: float
    defense: float
    hp: int
    level: float
    cp: int
    fast_move: str
    charged_moves: tuple[str, ...]

    @property
    def types(self) -> tuple[PokemonType, ...]:
        if self.secondary_type is None:
            return (self.primary_type,)
        return (self.primary_type, self.secondary_type)
