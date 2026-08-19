"""Transparent defensive/type-based scoring for V1."""

from dataclasses import dataclass
from statistics import fmean
from typing import Final

from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.scoring.config import (
    BASELINE_CONFIG,
    ResistanceCoverageStrategy,
    ScoreWeights,
    ScoringConfig,
    TeammateCoverageStrategy,
)
from pogo_team_optimizer.type_chart import (
    NEUTRAL,
    SUPER_EFFECTIVE,
    PokemonType,
    effectiveness,
)


TEAM_SIZE: Final = 3
TYPE_COUNT: Final = len(PokemonType)


@dataclass(frozen=True, slots=True)
class TeamScoreBreakdown:
    total_score: float
    ranking_quality: float
    shared_weakness_penalty: float
    severe_weakness_penalty: float
    resistance_coverage: float
    teammate_weakness_coverage: float
    defensive_diversity: float


def defensive_multipliers(team: tuple[RankingEntry, ...]) -> dict[PokemonType, tuple[float, ...]]:
    return {
        attacking_type: tuple(
            effectiveness(attacking_type, member.types) for member in team
        )
        for attacking_type in PokemonType
    }


def shared_weaknesses(team: tuple[RankingEntry, ...]) -> tuple[tuple[PokemonType, int], ...]:
    matrix = defensive_multipliers(team)
    return tuple(
        (attacking_type, sum(multiplier > NEUTRAL for multiplier in multipliers))
        for attacking_type, multipliers in matrix.items()
        if sum(multiplier > NEUTRAL for multiplier in multipliers) >= 2
    )


def resistance_types(team: tuple[RankingEntry, ...]) -> tuple[PokemonType, ...]:
    matrix = defensive_multipliers(team)
    return tuple(
        attacking_type
        for attacking_type, multipliers in matrix.items()
        if any(multiplier < NEUTRAL for multiplier in multipliers)
    )


def transform_resistance_coverage(
    raw_coverage: float, strategy: ResistanceCoverageStrategy, exponent: float
) -> float:
    """Apply a monotonic coverage transform configured for the experiment."""
    if not 0 <= raw_coverage <= 1:
        raise ValueError("raw_coverage must be between 0 and 1")
    if strategy is ResistanceCoverageStrategy.LINEAR:
        return raw_coverage
    if strategy is ResistanceCoverageStrategy.DIMINISHING:
        return raw_coverage**exponent
    raise ValueError(f"unsupported resistance strategy: {strategy}")


def exposure_aware_type_coverage(
    vulnerable_members: int, resistant_members: int
) -> float:
    """Score resistance supply relative to vulnerability for one attack type.

    The resistant share among non-neutral responses is normalized by 2/3, the
    maximum possible share when a three-member team has at least one weakness.
    Representative patterns therefore score as follows:
    weak/neutral/resist = 0.75, weak/weak/resist = 0.50,
    weak/resist/resist = 1.00, and weak/weak/neutral = 0.00.
    """
    if vulnerable_members < 0 or resistant_members < 0:
        raise ValueError("member counts cannot be negative")
    if vulnerable_members + resistant_members > TEAM_SIZE:
        raise ValueError("member counts cannot exceed team size")
    if vulnerable_members == 0:
        return 1.0
    if resistant_members == 0:
        return 0.0
    resistant_share = resistant_members / (vulnerable_members + resistant_members)
    return min(1.0, resistant_share / (2 / TEAM_SIZE))


def score_team(
    team: tuple[RankingEntry, ...],
    weights: ScoreWeights | None = None,
    config: ScoringConfig = BASELINE_CONFIG,
) -> TeamScoreBreakdown:
    """Score one unordered three-member team.

    Formula:
      + 35 * mean(PvPoke score / 100)
      + 25 * attack types resisted by at least one member / 18
      + 25 * weakness exposures covered by a resistant teammate / all exposures
      + 15 * mean defensive response diversity across 18 attacking types
      - 20 * attack types shared as weaknesses by 2+ members / 18
      - 15 * mean(triple-shared weakness rate, double-weakness exposure rate)
    """
    if len(team) != TEAM_SIZE:
        raise ValueError("V1 teams must contain exactly three Pokémon")

    effective_weights = weights or config.weights
    matrix = defensive_multipliers(team)
    ranking_quality = min(1.0, max(0.0, fmean(member.score for member in team) / 100))

    shared_count = 0
    triple_shared_count = 0
    double_weakness_exposures = 0
    resisted_type_count = 0
    weakness_exposures = 0
    covered_weakness_exposures = 0
    exposure_aware_coverage_total = 0.0
    diversity_total = 0.0

    double_weakness_threshold = SUPER_EFFECTIVE**2 - 1e-9
    for multipliers in matrix.values():
        weak_members = sum(multiplier > NEUTRAL for multiplier in multipliers)
        shared_count += weak_members >= 2
        triple_shared_count += weak_members == TEAM_SIZE
        double_weakness_exposures += sum(
            multiplier >= double_weakness_threshold for multiplier in multipliers
        )
        resisted_type_count += any(multiplier < NEUTRAL for multiplier in multipliers)
        resistant_members = sum(multiplier < NEUTRAL for multiplier in multipliers)
        if weak_members:
            exposure_aware_coverage_total += (
                weak_members
                * exposure_aware_type_coverage(weak_members, resistant_members)
            )

        for member_index, multiplier in enumerate(multipliers):
            if multiplier <= NEUTRAL:
                continue
            weakness_exposures += 1
            teammates = (
                teammate_multiplier
                for index, teammate_multiplier in enumerate(multipliers)
                if index != member_index
            )
            covered_weakness_exposures += any(
                teammate_multiplier < NEUTRAL for teammate_multiplier in teammates
            )

        response_categories = {
            -1 if multiplier < NEUTRAL else 1 if multiplier > NEUTRAL else 0
            for multiplier in multipliers
        }
        diversity_total += (len(response_categories) - 1) / (TEAM_SIZE - 1)

    shared_weakness_penalty = shared_count / TYPE_COUNT
    severe_weakness_penalty = fmean(
        (
            triple_shared_count / TYPE_COUNT,
            double_weakness_exposures / (TYPE_COUNT * TEAM_SIZE),
        )
    )
    raw_resistance_coverage = resisted_type_count / TYPE_COUNT
    resistance_coverage = transform_resistance_coverage(
        raw_resistance_coverage,
        config.resistance_strategy,
        config.resistance_exponent,
    )
    binary_teammate_coverage = (
        covered_weakness_exposures / weakness_exposures
        if weakness_exposures
        else 1.0
    )
    exposure_aware_coverage = (
        exposure_aware_coverage_total / weakness_exposures
        if weakness_exposures
        else 1.0
    )
    teammate_weakness_coverage = (
        binary_teammate_coverage
        if config.teammate_strategy is TeammateCoverageStrategy.BINARY
        else exposure_aware_coverage
    )
    defensive_diversity = diversity_total / TYPE_COUNT

    total_score = (
        effective_weights.ranking_quality * ranking_quality
        + effective_weights.resistance_coverage * resistance_coverage
        + effective_weights.teammate_weakness_coverage
        * teammate_weakness_coverage
        + effective_weights.defensive_diversity * defensive_diversity
        - effective_weights.shared_weakness_penalty * shared_weakness_penalty
        - effective_weights.severe_weakness_penalty * severe_weakness_penalty
    )
    return TeamScoreBreakdown(
        total_score=total_score,
        ranking_quality=ranking_quality,
        shared_weakness_penalty=shared_weakness_penalty,
        severe_weakness_penalty=severe_weakness_penalty,
        resistance_coverage=resistance_coverage,
        teammate_weakness_coverage=teammate_weakness_coverage,
        defensive_diversity=defensive_diversity,
    )
