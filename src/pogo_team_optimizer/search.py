"""Exhaustive, deterministic team search."""

from dataclasses import dataclass
from itertools import combinations
from math import comb
from collections.abc import Sequence

from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.scoring import (
    DEFAULT_WEIGHTS,
    ScoreWeights,
    TeamScoreBreakdown,
    resistance_types,
    score_team,
    shared_weaknesses,
)


@dataclass(frozen=True, slots=True)
class TeamEvaluation:
    members: tuple[RankingEntry, RankingEntry, RankingEntry]
    score: TeamScoreBreakdown
    shared_weaknesses: tuple[tuple[str, int], ...]
    resistance_coverage: tuple[str, ...]


def candidate_team_count(candidate_count: int) -> int:
    if candidate_count < 3:
        return 0
    return comb(candidate_count, 3)


def rank_teams(
    entries: Sequence[RankingEntry], weights: ScoreWeights = DEFAULT_WEIGHTS
) -> list[TeamEvaluation]:
    """Enumerate every unordered team and sort with stable deterministic ties."""
    evaluations: list[TeamEvaluation] = []
    for raw_team in combinations(entries, 3):
        team = (raw_team[0], raw_team[1], raw_team[2])
        evaluations.append(
            TeamEvaluation(
                members=team,
                score=score_team(team, weights),
                shared_weaknesses=tuple(
                    (attacking_type.value, count)
                    for attacking_type, count in shared_weaknesses(team)
                ),
                resistance_coverage=tuple(
                    attacking_type.value for attacking_type in resistance_types(team)
                ),
            )
        )

    evaluations.sort(
        key=lambda evaluation: (
            -evaluation.score.total_score,
            tuple(member.rank for member in evaluation.members),
            tuple(member.name.casefold() for member in evaluation.members),
        )
    )
    return evaluations
