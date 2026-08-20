"""V2.2a provisional inventory scouting and move-inspection priority."""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Sequence

from pogo_team_optimizer.inventory import (
    InventoryDiagnostic,
    readiness_by_instance,
)
from pogo_team_optimizer.models import InventoryPokemon, PokemonCandidate
from pogo_team_optimizer.readiness import ReadinessStatus
from pogo_team_optimizer.search_v2 import V2TeamEvaluation


class ScoutTeamClassification(StrEnum):
    NEEDS_MOVE_CHECK = "needs-move-check"
    POWER_UP_AND_MOVE_CHECK = "power-up+move-check"


@dataclass(frozen=True, slots=True)
class ScoutConfig:
    top_team_window: int = 50

    def __post_init__(self) -> None:
        if self.top_team_window < 1:
            raise ValueError("top_team_window must be at least 1")


DEFAULT_SCOUT_CONFIG: Final = ScoutConfig()


@dataclass(frozen=True, slots=True)
class InspectionPriority:
    instance_id: str
    pokemon_name: str
    species_id: str
    form: str | None
    shadow: bool
    cp: int
    source_rank: int
    readiness_status: ReadinessStatus
    top_team_frequency: int
    best_provisional_team_score: float | None
    best_provisional_team_rank: int | None
    actual_moves_known: bool
    frequency_score: float
    placement_score: float
    source_rank_score: float
    readiness_score: float
    inspection_priority: float


def provisional_team_classification(
    team: Sequence[PokemonCandidate],
    diagnostics: Sequence[InventoryDiagnostic],
) -> ScoutTeamClassification:
    assessments = readiness_by_instance(diagnostics)
    power_needed = any(
        assessments[member.instance_id].status
        in {
            ReadinessStatus.POWER_UP_NEEDED,
            ReadinessStatus.POWER_UP_AND_MOVE_CHECK,
        }
        for member in team
        if member.instance_id is not None
    )
    return (
        ScoutTeamClassification.POWER_UP_AND_MOVE_CHECK
        if power_needed
        else ScoutTeamClassification.NEEDS_MOVE_CHECK
    )


def rank_move_inspection_priorities(
    candidates: Sequence[PokemonCandidate],
    provisional_teams: Sequence[V2TeamEvaluation],
    inventory: Sequence[InventoryPokemon],
    diagnostics: Sequence[InventoryDiagnostic],
    config: ScoutConfig = DEFAULT_SCOUT_CONFIG,
) -> list[InspectionPriority]:
    """Rank unknown-move instances using only transparent global factors.

    priority = 0.40 frequency + 0.30 best placement + 0.20 source rank
             + 0.10 CP readiness.
    """
    unknown = [candidate for candidate in candidates if candidate.moves_provisional]
    inventory_by_id = {item.instance_id: item for item in inventory}
    assessments = readiness_by_instance(diagnostics)
    window = list(provisional_teams[: config.top_team_window])
    window_size = max(1, len(window))
    frequency: Counter[str] = Counter(
        member.instance_id
        for team in window
        for member in team.members
        if member.moves_provisional and member.instance_id is not None
    )
    best_rank: dict[str, int] = {}
    best_score: dict[str, float] = {}
    for team_rank, team in enumerate(provisional_teams, 1):
        for member in team.members:
            if not member.moves_provisional or member.instance_id is None:
                continue
            best_rank.setdefault(member.instance_id, team_rank)
            best_score.setdefault(member.instance_id, team.score.total_score)
    max_source_rank = max((candidate.rank for candidate in candidates), default=1)
    priorities: list[InspectionPriority] = []
    for candidate in unknown:
        instance_id = candidate.instance_id
        if instance_id is None:
            continue
        owned = inventory_by_id[instance_id]
        assessment = assessments[instance_id]
        count = frequency[instance_id]
        frequency_score = count / window_size
        placement = best_rank.get(instance_id)
        placement_score = (
            max(0.0, (window_size - placement + 1) / window_size)
            if placement is not None and placement <= window_size
            else 0.0
        )
        source_rank_score = (
            1.0
            if max_source_rank == 1
            else 1 - (candidate.rank - 1) / (max_source_rank - 1)
        )
        readiness_score = (
            1.0
            if assessment.status is ReadinessStatus.NEEDS_MOVE_CHECK
            else 0.5
            if assessment.status is ReadinessStatus.POWER_UP_AND_MOVE_CHECK
            else 0.0
        )
        priority = (
            0.40 * frequency_score
            + 0.30 * placement_score
            + 0.20 * source_rank_score
            + 0.10 * readiness_score
        )
        priorities.append(
            InspectionPriority(
                instance_id,
                candidate.name,
                candidate.species_id,
                owned.form,
                owned.shadow,
                owned.cp,
                candidate.rank,
                assessment.status,
                count,
                best_score.get(instance_id),
                placement,
                False,
                frequency_score,
                placement_score,
                source_rank_score,
                readiness_score,
                priority,
            )
        )
    priorities.sort(
        key=lambda item: (
            -item.inspection_priority,
            item.best_provisional_team_rank or 10**9,
            item.source_rank,
            item.instance_id,
        )
    )
    return priorities
