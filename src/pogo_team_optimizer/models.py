"""Normalized, source-independent domain models."""

from dataclasses import dataclass
from enum import StrEnum

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


class MoveKind(StrEnum):
    FAST = "fast"
    CHARGED = "charged"


@dataclass(frozen=True, slots=True)
class Move:
    move_id: str
    name: str
    move_type: PokemonType
    kind: MoveKind
    power: float
    energy: float
    energy_gain: float
    cooldown: float = 0.0
    turns: int = 1
    buffs: tuple[int, ...] = ()
    buff_target: str | None = None
    buff_apply_chance: float | None = None


@dataclass(frozen=True, slots=True)
class PokemonCandidate:
    """A ranking row composed with resolved move metadata."""

    ranking: RankingEntry
    species_id: str
    team_species_key: str
    fast_move: Move
    charged_moves: tuple[Move, ...]
    instance_id: str | None = None
    recommended_fast_move: Move | None = None
    recommended_charged_moves: tuple[Move, ...] = ()

    @property
    def name(self) -> str:
        return self.ranking.name

    @property
    def rank(self) -> int:
        return self.ranking.rank

    @property
    def types(self) -> tuple[PokemonType, ...]:
        return self.ranking.types

    @property
    def moves(self) -> tuple[Move, ...]:
        return (self.fast_move, *self.charged_moves)

    @property
    def recommended_moves(self) -> tuple[Move, ...]:
        return (
            self.recommended_fast_move or self.fast_move,
            *(self.recommended_charged_moves or self.charged_moves),
        )

    def has_stab(self, move: Move) -> bool:
        return move.move_type in self.types


@dataclass(frozen=True, slots=True)
class InventoryPokemon:
    instance_id: str
    pokemon_name: str
    form: str | None
    shadow: bool
    cp: int
    fast_move: str | None
    charged_move_1: str | None
    charged_move_2: str | None
    notes: str = ""

    @property
    def move_names(self) -> tuple[str, ...]:
        return tuple(
            move
            for move in (self.fast_move, self.charged_move_1, self.charged_move_2)
            if move
        )
