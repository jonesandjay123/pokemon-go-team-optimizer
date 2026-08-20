"""Deterministic exhaustive search over theoretical or inventory candidates."""

from dataclasses import dataclass
from itertools import combinations
from collections.abc import Sequence

from pogo_team_optimizer.models import PokemonCandidate
from pogo_team_optimizer.scoring.v2 import V2ScoreBreakdown, score_v2_team
from pogo_team_optimizer.scoring.v21 import V21ScoreBreakdown, score_v21_team


@dataclass(frozen=True, slots=True)
class V2TeamEvaluation:
    members: tuple[PokemonCandidate, PokemonCandidate, PokemonCandidate]
    score: V2ScoreBreakdown | V21ScoreBreakdown


def is_legal_team(team: tuple[PokemonCandidate, ...]) -> bool:
    """Enforce unique instances and the GBL species clause (dex identity)."""
    instance_ids = [member.instance_id for member in team if member.instance_id]
    return (
        len(instance_ids) == len(set(instance_ids))
        and len({member.team_species_key for member in team}) == len(team)
    )


def rank_v2_teams(
    candidates: Sequence[PokemonCandidate], scoring: str = "v2"
) -> list[V2TeamEvaluation]:
    if scoring not in {"v2", "v2.1"}:
        raise ValueError(f"unsupported move-aware scoring: {scoring}")
    scorer = score_v21_team if scoring == "v2.1" else score_v2_team
    evaluations = [
        V2TeamEvaluation((team[0], team[1], team[2]), scorer(team))
        for team in combinations(candidates, 3)
        if is_legal_team(team)
    ]
    evaluations.sort(
        key=lambda value: (
            -value.score.total_score,
            tuple(member.rank for member in value.members),
            tuple((member.instance_id or "", member.name.casefold()) for member in value.members),
        )
    )
    return evaluations
