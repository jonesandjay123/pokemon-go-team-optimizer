"""Transparent scoring components for team evaluation."""

from pogo_team_optimizer.scoring.config import (
    BASELINE_CONFIG,
    COMBINED_CONFIG,
    DEFAULT_WEIGHTS,
    DIMINISHING_RESISTANCE_CONFIG,
    EXPOSURE_AWARE_CONFIG,
    SCORING_CONFIGS,
    SEVERE_PENALTY_CONFIG,
    ResistanceCoverageStrategy,
    ScoreWeights,
    ScoringConfig,
    ScoringName,
    TeammateCoverageStrategy,
    get_scoring_config,
)
from pogo_team_optimizer.scoring.v1 import (
    TeamScoreBreakdown,
    exposure_aware_type_coverage,
    resistance_types,
    score_team,
    shared_weaknesses,
    transform_resistance_coverage,
)

__all__ = [
    "BASELINE_CONFIG",
    "COMBINED_CONFIG",
    "DEFAULT_WEIGHTS",
    "DIMINISHING_RESISTANCE_CONFIG",
    "EXPOSURE_AWARE_CONFIG",
    "SCORING_CONFIGS",
    "SEVERE_PENALTY_CONFIG",
    "ResistanceCoverageStrategy",
    "ScoreWeights",
    "ScoringConfig",
    "ScoringName",
    "TeammateCoverageStrategy",
    "TeamScoreBreakdown",
    "exposure_aware_type_coverage",
    "get_scoring_config",
    "resistance_types",
    "score_team",
    "shared_weaknesses",
    "transform_resistance_coverage",
]
