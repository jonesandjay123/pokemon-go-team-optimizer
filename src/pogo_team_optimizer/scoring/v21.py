"""V2.1 inventory-correctness scoring without battle simulation."""

from dataclasses import dataclass
from statistics import fmean
from typing import Final

from pogo_team_optimizer.models import PokemonCandidate
from pogo_team_optimizer.scoring.move_quality import MovesetQuality, score_moveset_quality
from pogo_team_optimizer.scoring.v2 import V2ScoreBreakdown, score_v2_team


MOVE_QUALITY_ADJUSTMENT_WEIGHT: Final = 20.0


@dataclass(frozen=True, slots=True)
class CandidateMoveQuality:
    instance_id: str | None
    actual: MovesetQuality
    recommended: MovesetQuality
    delta: float


@dataclass(frozen=True, slots=True)
class V21ScoreBreakdown:
    total_score: float
    v2_score: V2ScoreBreakdown
    member_move_quality: tuple[CandidateMoveQuality, ...]
    actual_move_quality: float
    recommended_move_quality: float
    move_quality_delta: float
    move_quality_adjustment: float


def candidate_move_quality(candidate: PokemonCandidate) -> CandidateMoveQuality:
    actual = score_moveset_quality(candidate.fast_move, candidate.charged_moves)
    recommended_fast = candidate.recommended_fast_move or candidate.fast_move
    recommended_charged = (
        candidate.recommended_charged_moves or candidate.charged_moves
    )
    recommended = score_moveset_quality(recommended_fast, recommended_charged)
    return CandidateMoveQuality(
        candidate.instance_id,
        actual,
        recommended,
        actual.total_score - recommended.total_score,
    )


def score_v21_team(team: tuple[PokemonCandidate, ...]) -> V21ScoreBreakdown:
    if len(team) != 3:
        raise ValueError("V2.1 teams must contain exactly three Pokémon")
    v2 = score_v2_team(team)
    members = tuple(candidate_move_quality(candidate) for candidate in team)
    actual = fmean(value.actual.total_score for value in members)
    recommended = fmean(value.recommended.total_score for value in members)
    delta = actual - recommended
    adjustment = MOVE_QUALITY_ADJUSTMENT_WEIGHT * delta
    return V21ScoreBreakdown(
        v2.total_score + adjustment,
        v2,
        members,
        actual,
        recommended,
        delta,
        adjustment,
    )
