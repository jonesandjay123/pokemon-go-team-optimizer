"""Transparent defensive/type-based scoring for V1."""

from dataclasses import dataclass
from statistics import fmean
from typing import Final

from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.type_chart import (
    NEUTRAL,
    SUPER_EFFECTIVE,
    PokemonType,
    effectiveness,
)


TEAM_SIZE: Final = 3
TYPE_COUNT: Final = len(PokemonType)


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    """Tunable V1 weights; all raw components are normalized to 0..1."""

    ranking_quality: float = 35.0
    resistance_coverage: float = 25.0
    teammate_weakness_coverage: float = 25.0
    defensive_diversity: float = 15.0
    shared_weakness_penalty: float = 20.0
    severe_weakness_penalty: float = 15.0


DEFAULT_WEIGHTS: Final = ScoreWeights()


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


def score_team(
    team: tuple[RankingEntry, ...], weights: ScoreWeights = DEFAULT_WEIGHTS
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

    matrix = defensive_multipliers(team)
    ranking_quality = min(1.0, max(0.0, fmean(member.score for member in team) / 100))

    shared_count = 0
    triple_shared_count = 0
    double_weakness_exposures = 0
    resisted_type_count = 0
    weakness_exposures = 0
    covered_weakness_exposures = 0
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
    resistance_coverage = resisted_type_count / TYPE_COUNT
    teammate_weakness_coverage = (
        covered_weakness_exposures / weakness_exposures
        if weakness_exposures
        else 1.0
    )
    defensive_diversity = diversity_total / TYPE_COUNT

    total_score = (
        weights.ranking_quality * ranking_quality
        + weights.resistance_coverage * resistance_coverage
        + weights.teammate_weakness_coverage * teammate_weakness_coverage
        + weights.defensive_diversity * defensive_diversity
        - weights.shared_weakness_penalty * shared_weakness_penalty
        - weights.severe_weakness_penalty * severe_weakness_penalty
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
