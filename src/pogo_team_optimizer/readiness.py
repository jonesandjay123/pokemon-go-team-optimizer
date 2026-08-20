"""Inventory battle-readiness classification for V2.2.

CP ratio is a transparent buildability heuristic, not a combat-performance or
IV simulation model.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class ReadinessStatus(StrEnum):
    READY_NOW = "ready-now"
    POWER_UP_NEEDED = "power-up-needed"
    INELIGIBLE_OVER_CAP = "ineligible-over-cap"
    INVALID_MISSING_MOVE = "invalid/missing-move"
    MISSING_SPECIES_FORM = "missing-species/form"
    NEEDS_MOVE_CHECK = "needs-move-check"
    POWER_UP_AND_MOVE_CHECK = "power-up+move-check"


class TargetCpSource(StrEnum):
    RANKING = "ranking-target"
    LEAGUE_CAP_FALLBACK = "league-cap-fallback"


@dataclass(frozen=True, slots=True)
class ReadinessConfig:
    ready_ratio_threshold: float = 0.95

    def __post_init__(self) -> None:
        if not 0 < self.ready_ratio_threshold <= 1:
            raise ValueError("ready_ratio_threshold must be greater than 0 and at most 1")


DEFAULT_READINESS_CONFIG: Final = ReadinessConfig()


@dataclass(frozen=True, slots=True)
class ReadinessAssessment:
    actual_cp: int
    target_cp: int
    cp_gap: int
    readiness_ratio: float
    status: ReadinessStatus
    target_source: TargetCpSource


def preferred_target_cp(
    ranking_cp: int, league_cp_cap: int
) -> tuple[int, TargetCpSource]:
    if 0 < ranking_cp <= league_cp_cap:
        return ranking_cp, TargetCpSource.RANKING
    return league_cp_cap, TargetCpSource.LEAGUE_CAP_FALLBACK


def assess_readiness(
    actual_cp: int,
    ranking_cp: int,
    league_cp_cap: int,
    config: ReadinessConfig = DEFAULT_READINESS_CONFIG,
    invalid_status: ReadinessStatus | None = None,
) -> ReadinessAssessment:
    if actual_cp <= 0:
        raise ValueError("actual_cp must be greater than 0")
    if league_cp_cap <= 0:
        raise ValueError("league_cp_cap must be greater than 0")
    target_cp, source = preferred_target_cp(ranking_cp, league_cp_cap)
    ratio = actual_cp / target_cp
    if invalid_status is not None:
        status = invalid_status
    elif actual_cp > league_cp_cap:
        status = ReadinessStatus.INELIGIBLE_OVER_CAP
    elif ratio >= config.ready_ratio_threshold:
        status = ReadinessStatus.READY_NOW
    else:
        status = ReadinessStatus.POWER_UP_NEEDED
    return ReadinessAssessment(
        actual_cp=actual_cp,
        target_cp=target_cp,
        cp_gap=max(0, target_cp - actual_cp),
        readiness_ratio=ratio,
        status=status,
        target_source=source,
    )


def assess_unknown_moves_readiness(
    actual_cp: int,
    ranking_cp: int,
    league_cp_cap: int,
    config: ReadinessConfig = DEFAULT_READINESS_CONFIG,
) -> ReadinessAssessment:
    base = assess_readiness(actual_cp, ranking_cp, league_cp_cap, config)
    if base.status is ReadinessStatus.READY_NOW:
        status = ReadinessStatus.NEEDS_MOVE_CHECK
    elif base.status is ReadinessStatus.POWER_UP_NEEDED:
        status = ReadinessStatus.POWER_UP_AND_MOVE_CHECK
    else:
        status = base.status
    return ReadinessAssessment(
        base.actual_cp,
        base.target_cp,
        base.cp_gap,
        base.readiness_ratio,
        status,
        base.target_source,
    )
