"""Machine-readable V2 versus V1/V1.1 diagnostics."""

from collections import Counter
from statistics import fmean
from collections.abc import Mapping, Sequence

from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.scoring import SCORING_CONFIGS, ScoringName
from pogo_team_optimizer.search import TeamEvaluation, rank_teams
from pogo_team_optimizer.search_v2 import V2TeamEvaluation
from pogo_team_optimizer.type_chart import PokemonType


def _team_key(members) -> tuple[str, ...]:
    return tuple(sorted(member.name for member in members))


def _frequencies(evaluations, limit: int = 50) -> Counter[str]:
    return Counter(member.name for team in evaluations[:limit] for member in team.members)


def _best_member_positions(evaluations) -> dict[str, int]:
    positions: dict[str, int] = {}
    for rank, team in enumerate(evaluations, 1):
        for member in team.members:
            positions.setdefault(member.name, rank)
    return positions


def build_v2_diagnostics(
    entries: Sequence[RankingEntry], v2: Sequence[V2TeamEvaluation]
) -> dict[str, object]:
    v1_models: Mapping[ScoringName, list[TeamEvaluation]] = {
        name: rank_teams(entries, scoring_config=config)
        for name, config in SCORING_CONFIGS.items()
    }
    baseline = v1_models[ScoringName.BASELINE]
    v2_top10 = {_team_key(team.members) for team in v2[:10]}
    comparisons = {}
    for name, evaluations in v1_models.items():
        top10 = {_team_key(team.members) for team in evaluations[:10]}
        comparisons[name.value] = {
            "top_10_overlap": len(top10 & v2_top10),
            "top_10_different": 10 - len(top10 & v2_top10),
        }
    baseline_frequency = _frequencies(baseline)
    v2_frequency = _frequencies(v2)
    frequency_changes = sorted(
        (
            {"pokemon": name, "v1": baseline_frequency[name], "v2": v2_frequency[name], "delta": v2_frequency[name] - baseline_frequency[name]}
            for name in set(baseline_frequency) | set(v2_frequency)
        ),
        key=lambda item: (-abs(item["delta"]), item["pokemon"]),
    )
    baseline_positions = _best_member_positions(baseline)
    v2_positions = _best_member_positions(v2)
    movement = sorted(
        (
            {"pokemon": name, "v1_best_team_rank": baseline_positions[name], "v2_best_team_rank": v2_positions[name], "improvement": baseline_positions[name] - v2_positions[name]}
            for name in baseline_positions
        ),
        key=lambda item: (-item["improvement"], item["pokemon"]),
    )
    top50 = v2[:50]
    fields = (
        "unique_offensive_type_coverage", "super_effective_coverage",
        "charged_move_coverage", "fast_move_coverage", "stab_move_availability",
        "offensive_redundancy", "defensive_offensive_balance",
    )
    distributions = {}
    for field in fields:
        values = [getattr(team.score, field) for team in top50]
        distributions[field] = {"min": min(values), "mean": fmean(values), "max": max(values)}
    target_aliases = (
        {"Tinkaton", "巨鍛匠"},
        {"Guzzlord", "惡食大王"},
        {"Talonflame", "烈箭鷹"},
    )
    target_names = tuple(
        next((entry.name for entry in entries if entry.name in aliases), "")
        for aliases in target_aliases
    )
    target = tuple(sorted(target_names)) if all(target_names) else None
    target_comparison = None
    if target:
        v2_rank, target_team = next(
            (rank, team)
            for rank, team in enumerate(v2, 1)
            if _team_key(team.members) == target
        )
        target_comparison = {
            "team": list(target_names),
            "v2_rank": v2_rank,
            "v2_score": target_team.score.total_score,
            "v2_components": {
                field: getattr(target_team.score, field) for field in fields
            },
            "v1_placements": {
                name.value: next(
                    rank
                    for rank, team in enumerate(evaluations, 1)
                    if _team_key(team.members) == target
                )
                for name, evaluations in v1_models.items()
            },
        }
    return {
        "v2_top_10": [[member.name for member in team.members] for team in v2[:10]],
        "comparisons": comparisons,
        "frequency_changes": frequency_changes,
        "steel_prevalence_top_50": sum(any(PokemonType.STEEL in member.types for member in team.members) for team in top50) / len(top50),
        "flying_prevalence_top_50": sum(any(PokemonType.FLYING in member.types for member in team.members) for team in top50) / len(top50),
        "offensive_coverage_distributions": distributions,
        "largest_improvements": movement[:10],
        "largest_declines": list(reversed(movement[-10:])),
        "specified_v1_number_one": target_comparison,
    }
