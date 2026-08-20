"""Transparent, species-agnostic PvP moveset quality heuristics for V2.1."""

from dataclasses import dataclass
from statistics import fmean

from pogo_team_optimizer.models import Move


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return min(maximum, max(minimum, value))


@dataclass(frozen=True, slots=True)
class FastMoveQuality:
    damage_per_turn: float
    energy_per_turn: float
    timing_responsiveness: float
    damage_score: float
    energy_score: float
    total_score: float


@dataclass(frozen=True, slots=True)
class ChargedMoveQuality:
    move_id: str
    damage_per_energy: float
    power_score: float
    damage_per_energy_score: float
    affordability_score: float
    buff_utility: float
    total_score: float


@dataclass(frozen=True, slots=True)
class MovesetQuality:
    total_score: float
    fast_move: FastMoveQuality
    charged_moves: tuple[ChargedMoveQuality, ...]
    charged_quality: float
    charged_slot_completeness: float


def score_fast_move_quality(move: Move) -> FastMoveQuality:
    """Normalize DPT/EPT against strong-but-reachable PvP values of 5."""
    turns = max(1, move.turns)
    damage_per_turn = move.power / turns
    energy_per_turn = move.energy_gain / turns
    damage_score = _clamp(damage_per_turn / 5)
    energy_score = _clamp(energy_per_turn / 5)
    timing = 1 / turns
    total = 0.4 * damage_score + 0.5 * energy_score + 0.1 * timing
    return FastMoveQuality(
        damage_per_turn,
        energy_per_turn,
        timing,
        damage_score,
        energy_score,
        total,
    )


def _buff_utility(move: Move) -> float:
    """Return signed expected stage utility, normalized to -1..1."""
    if not move.buffs:
        return 0.0
    direction = -1 if move.buff_target == "opponent" else 1
    chance = move.buff_apply_chance if move.buff_apply_chance is not None else 1.0
    return _clamp(direction * sum(move.buffs) * chance / 4, -1, 1)


def score_charged_move_quality(move: Move) -> ChargedMoveQuality:
    energy = max(1.0, move.energy)
    damage_per_energy = move.power / energy
    power_score = _clamp(move.power / 150)
    dpe_score = _clamp(damage_per_energy / 2.5)
    # 35 energy is exceptionally cheap and 100 is the practical upper bound.
    affordability = _clamp((100 - energy) / 65)
    buff_utility = _buff_utility(move)
    total = _clamp(
        0.20 * power_score
        + 0.55 * dpe_score
        + 0.25 * affordability
        + 0.10 * buff_utility
    )
    return ChargedMoveQuality(
        move.move_id,
        damage_per_energy,
        power_score,
        dpe_score,
        affordability,
        buff_utility,
        total,
    )


def score_moveset_quality(
    fast_move: Move, charged_moves: tuple[Move, ...]
) -> MovesetQuality:
    if not 1 <= len(charged_moves) <= 2:
        raise ValueError("a V2.1 moveset must have one or two charged moves")
    fast = score_fast_move_quality(fast_move)
    charged = tuple(score_charged_move_quality(move) for move in charged_moves)
    charged_quality = fmean(move.total_score for move in charged)
    completeness = len(charged) / 2
    total = 0.40 * fast.total_score + 0.45 * charged_quality + 0.15 * completeness
    return MovesetQuality(total, fast, charged, charged_quality, completeness)
