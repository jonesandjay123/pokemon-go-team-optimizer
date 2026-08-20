"""Transparent move-aware offensive coverage scoring (no battle simulation)."""

from dataclasses import dataclass
from itertools import combinations
from statistics import fmean
from typing import Final, Iterable

from pogo_team_optimizer.models import Move, PokemonCandidate
from pogo_team_optimizer.scoring.v1 import TeamScoreBreakdown, score_team
from pogo_team_optimizer.type_chart import NEUTRAL, PokemonType, effectiveness


@dataclass(frozen=True, slots=True)
class V2Weights:
    unique_offensive_types: float = 10.0
    super_effective_coverage: float = 15.0
    charged_move_coverage: float = 10.0
    fast_move_coverage: float = 5.0
    stab_availability: float = 5.0
    defensive_offensive_balance: float = 10.0
    offensive_redundancy_penalty: float = 10.0


V2_DEFAULT_WEIGHTS: Final = V2Weights()


@dataclass(frozen=True, slots=True)
class CoverageSummary:
    super_effective: tuple[PokemonType, ...]
    neutral: tuple[PokemonType, ...]
    resisted: tuple[PokemonType, ...]


@dataclass(frozen=True, slots=True)
class V2ScoreBreakdown:
    total_score: float
    defensive_score: TeamScoreBreakdown
    unique_offensive_type_coverage: float
    super_effective_coverage: float
    charged_move_coverage: float
    fast_move_coverage: float
    stab_move_availability: float
    offensive_redundancy: float
    defensive_offensive_balance: float
    all_move_summary: CoverageSummary
    charged_move_summary: CoverageSummary
    fast_move_summary: CoverageSummary


def coverage_summary(
    moves: Iterable[Move],
    defending_types: Iterable[tuple[PokemonType, ...]] | None = None,
) -> CoverageSummary:
    """Classify targets by the best available move; dual types are supported."""
    move_tuple = tuple(moves)
    targets = tuple(defending_types or ((value,) for value in PokemonType))
    super_effective: list[PokemonType] = []
    neutral: list[PokemonType] = []
    resisted: list[PokemonType] = []
    # Public team metrics use the 18 single-type targets. For a supplied dual
    # target list, the first type is a stable label while the multiplier still
    # uses the complete tuple.
    for target in targets:
        best = max((effectiveness(move.move_type, target) for move in move_tuple), default=0)
        bucket = super_effective if best > NEUTRAL else neutral if best == NEUTRAL else resisted
        bucket.append(target[0])
    return CoverageSummary(tuple(super_effective), tuple(neutral), tuple(resisted))


def offensive_redundancy(team: tuple[PokemonCandidate, ...]) -> float:
    """Mean pairwise Jaccard overlap of teammates' offensive move types."""
    overlaps: list[float] = []
    for left, right in combinations(team, 2):
        left_types = {move.move_type for move in left.moves}
        right_types = {move.move_type for move in right.moves}
        union = left_types | right_types
        overlaps.append(len(left_types & right_types) / len(union) if union else 0)
    return fmean(overlaps) if overlaps else 0


def score_v2_team(
    team: tuple[PokemonCandidate, ...], weights: V2Weights = V2_DEFAULT_WEIGHTS
) -> V2ScoreBreakdown:
    if len(team) != 3:
        raise ValueError("V2 teams must contain exactly three Pokémon")
    all_moves = tuple(move for member in team for move in member.moves)
    fast_moves = tuple(member.fast_move for member in team)
    charged_moves = tuple(move for member in team for move in member.charged_moves)
    all_summary = coverage_summary(all_moves)
    fast_summary = coverage_summary(fast_moves)
    charged_summary = coverage_summary(charged_moves)
    type_count = len(PokemonType)
    unique_types = len({move.move_type for move in all_moves}) / type_count
    super_coverage = len(all_summary.super_effective) / type_count
    fast_coverage = len(fast_summary.super_effective) / type_count
    charged_coverage = len(charged_summary.super_effective) / type_count
    stab = sum(any(member.has_stab(move) for move in member.moves) for member in team) / 3
    redundancy = offensive_redundancy(team)
    defensive = score_team(tuple(member.ranking for member in team))
    offensive_strength = fmean((super_coverage, fast_coverage, charged_coverage))
    balance = 1 - abs(min(1.0, max(0.0, defensive.total_score / 100)) - offensive_strength)
    total = (
        defensive.total_score
        + weights.unique_offensive_types * unique_types
        + weights.super_effective_coverage * super_coverage
        + weights.charged_move_coverage * charged_coverage
        + weights.fast_move_coverage * fast_coverage
        + weights.stab_availability * stab
        + weights.defensive_offensive_balance * balance
        - weights.offensive_redundancy_penalty * redundancy
    )
    return V2ScoreBreakdown(
        total, defensive, unique_types, super_coverage, charged_coverage,
        fast_coverage, stab, redundancy, balance, all_summary,
        charged_summary, fast_summary,
    )
