"""Deterministic exhaustive search over theoretical or inventory candidates."""

from dataclasses import dataclass
from itertools import combinations
from collections.abc import Sequence

from pogo_team_optimizer.models import PokemonCandidate
from pogo_team_optimizer.scoring.v2 import V2ScoreBreakdown, score_v2_team


@dataclass(frozen=True, slots=True)
class V2TeamEvaluation:
    members: tuple[PokemonCandidate, PokemonCandidate, PokemonCandidate]
    score: V2ScoreBreakdown


def rank_v2_teams(candidates: Sequence[PokemonCandidate]) -> list[V2TeamEvaluation]:
    evaluations = [
        V2TeamEvaluation((team[0], team[1], team[2]), score_v2_team(team))
        for team in combinations(candidates, 3)
        # An inventory cannot place the exact same owned instance twice.
        if len({member.instance_id for member in team if member.instance_id})
        == sum(member.instance_id is not None for member in team)
    ]
    evaluations.sort(
        key=lambda value: (
            -value.score.total_score,
            tuple(member.rank for member in value.members),
            tuple((member.instance_id or "", member.name.casefold()) for member in value.members),
        )
    )
    return evaluations
