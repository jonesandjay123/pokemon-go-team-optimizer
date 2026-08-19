"""Configuration and strategy selection for V1/V1.1 scoring models."""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final


class ScoringName(StrEnum):
    BASELINE = "baseline"
    DIMINISHING_RESISTANCE = "diminishing-resistance"
    EXPOSURE_AWARE = "exposure-aware"
    COMBINED = "combined"
    SEVERE_PENALTY = "severe-penalty"


class ResistanceCoverageStrategy(StrEnum):
    LINEAR = "linear"
    DIMINISHING = "diminishing"


class TeammateCoverageStrategy(StrEnum):
    BINARY = "binary"
    EXPOSURE_AWARE = "exposure-aware"


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    """Tunable weights; every raw scoring component is normalized to 0..1."""

    ranking_quality: float = 35.0
    resistance_coverage: float = 25.0
    teammate_weakness_coverage: float = 25.0
    defensive_diversity: float = 15.0
    shared_weakness_penalty: float = 20.0
    severe_weakness_penalty: float = 15.0


DEFAULT_WEIGHTS: Final = ScoreWeights()


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """One reproducible scoring experiment without team-specific exceptions."""

    name: ScoringName
    weights: ScoreWeights = DEFAULT_WEIGHTS
    resistance_strategy: ResistanceCoverageStrategy = (
        ResistanceCoverageStrategy.LINEAR
    )
    resistance_exponent: float = 1.0
    teammate_strategy: TeammateCoverageStrategy = TeammateCoverageStrategy.BINARY

    def __post_init__(self) -> None:
        if not 0 < self.resistance_exponent <= 1:
            raise ValueError("resistance_exponent must be greater than 0 and at most 1")


BASELINE_CONFIG: Final = ScoringConfig(name=ScoringName.BASELINE)
DIMINISHING_RESISTANCE_CONFIG: Final = ScoringConfig(
    name=ScoringName.DIMINISHING_RESISTANCE,
    resistance_strategy=ResistanceCoverageStrategy.DIMINISHING,
    resistance_exponent=0.5,
)
EXPOSURE_AWARE_CONFIG: Final = ScoringConfig(
    name=ScoringName.EXPOSURE_AWARE,
    teammate_strategy=TeammateCoverageStrategy.EXPOSURE_AWARE,
)
COMBINED_CONFIG: Final = ScoringConfig(
    name=ScoringName.COMBINED,
    resistance_strategy=ResistanceCoverageStrategy.DIMINISHING,
    resistance_exponent=0.5,
    teammate_strategy=TeammateCoverageStrategy.EXPOSURE_AWARE,
)
SEVERE_PENALTY_CONFIG: Final = ScoringConfig(
    name=ScoringName.SEVERE_PENALTY,
    weights=replace(DEFAULT_WEIGHTS, severe_weakness_penalty=45.0),
)

SCORING_CONFIGS: Final[dict[ScoringName, ScoringConfig]] = {
    config.name: config
    for config in (
        BASELINE_CONFIG,
        DIMINISHING_RESISTANCE_CONFIG,
        EXPOSURE_AWARE_CONFIG,
        COMBINED_CONFIG,
        SEVERE_PENALTY_CONFIG,
    )
}


def get_scoring_config(name: str | ScoringName) -> ScoringConfig:
    return SCORING_CONFIGS[ScoringName(name)]
