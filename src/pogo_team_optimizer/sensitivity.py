"""V1.1 sensitivity analysis across reproducible scoring configurations."""

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean, median
from typing import Any

from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.output import write_top_teams
from pogo_team_optimizer.scoring import SCORING_CONFIGS, ScoringConfig, ScoringName
from pogo_team_optimizer.search import TeamEvaluation, rank_teams


COMPARISON_FIELDS = (
    "scoring",
    "top_team",
    "top_score",
    "steel_team_pct",
    "flying_team_pct",
    "steel_and_flying_team_pct",
    "water_team_pct",
    "all_dual_type_team_pct",
    "zero_shared_weakness_teams",
    "mean_source_rank_top10",
    "median_source_rank_top10",
    "worst_source_rank_top10",
    "pvpoke_top3_optimizer_rank",
    "baseline_top10_overlap",
    "baseline_top50_overlap",
    "baseline_top50_jaccard",
)


def team_key(evaluation: TeamEvaluation) -> tuple[int, int, int]:
    return tuple(member.rank for member in evaluation.members)  # type: ignore[return-value]


def grouped_species_name(name: str) -> str:
    """Group a Shadow entry with its otherwise identical source species/form."""
    return name.removesuffix(" 暗影")


def _contains_type(evaluation: TeamEvaluation, type_name: str) -> bool:
    return any(
        pokemon_type.value == type_name
        for member in evaluation.members
        for pokemon_type in member.types
    )


def _distribution(values: Sequence[float | int]) -> dict[str, int]:
    counts = Counter(
        str(value) if isinstance(value, int) else f"{value:.6f}" for value in values
    )
    return dict(sorted(counts.items(), key=lambda item: float(item[0])))


def _ordered_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _model_summary(evaluations: Sequence[TeamEvaluation]) -> dict[str, Any]:
    top10 = evaluations[:10]
    top50 = evaluations[:50]
    exact_frequency = Counter(
        member.name for evaluation in top50 for member in evaluation.members
    )
    grouped_frequency = Counter(
        grouped_species_name(member.name)
        for evaluation in top50
        for member in evaluation.members
    )
    source_ranks = [
        member.rank for evaluation in top10 for member in evaluation.members
    ]
    worst_rank = max(source_ranks)
    worst_members = sorted(
        {
            member.name
            for evaluation in top10
            for member in evaluation.members
            if member.rank == worst_rank
        }
    )
    pvpoke_top3_rank = next(
        rank
        for rank, evaluation in enumerate(evaluations, start=1)
        if team_key(evaluation) == (1, 2, 3)
    )

    return {
        "top_10": [
            {
                "rank": rank,
                "team": [member.name for member in evaluation.members],
                "source_ranks": [member.rank for member in evaluation.members],
                "total_score": round(evaluation.score.total_score, 6),
                "components": {
                    "ranking_quality": round(evaluation.score.ranking_quality, 6),
                    "resistance_coverage": round(
                        evaluation.score.resistance_coverage, 6
                    ),
                    "teammate_weakness_coverage": round(
                        evaluation.score.teammate_weakness_coverage, 6
                    ),
                    "defensive_diversity": round(
                        evaluation.score.defensive_diversity, 6
                    ),
                    "shared_weakness_penalty": round(
                        evaluation.score.shared_weakness_penalty, 6
                    ),
                    "severe_weakness_penalty": round(
                        evaluation.score.severe_weakness_penalty, 6
                    ),
                },
            }
            for rank, evaluation in enumerate(top10, start=1)
        ],
        "top_50_frequency": _ordered_counter(exact_frequency),
        "top_50_frequency_grouped": _ordered_counter(grouped_frequency),
        "structure": {
            "steel_team_pct": fmean(
                _contains_type(evaluation, "steel") for evaluation in top50
            ),
            "flying_team_pct": fmean(
                _contains_type(evaluation, "flying") for evaluation in top50
            ),
            "steel_and_flying_team_pct": fmean(
                _contains_type(evaluation, "steel")
                and _contains_type(evaluation, "flying")
                for evaluation in top50
            ),
            "water_team_pct": fmean(
                _contains_type(evaluation, "water") for evaluation in top50
            ),
            "all_dual_type_team_pct": fmean(
                all(len(member.types) == 2 for member in evaluation.members)
                for evaluation in top50
            ),
            "zero_shared_weakness_teams": sum(
                not evaluation.shared_weaknesses for evaluation in top50
            ),
        },
        "resistance_type_count_distribution": _distribution(
            [len(evaluation.resistance_coverage) for evaluation in top50]
        ),
        "resistance_score_distribution": _distribution(
            [evaluation.score.resistance_coverage for evaluation in top50]
        ),
        "teammate_coverage_distribution": _distribution(
            [evaluation.score.teammate_weakness_coverage for evaluation in top50]
        ),
        "source_rank_top10": {
            "mean": fmean(source_ranks),
            "median": median(source_ranks),
            "worst_rank": worst_rank,
            "worst_ranked_pokemon": worst_members,
        },
        "pvpoke_top3_optimizer_rank": pvpoke_top3_rank,
    }


def _frequency_changes(
    baseline: Mapping[str, int], variant: Mapping[str, int]
) -> dict[str, int]:
    names = set(baseline) | set(variant)
    changes = {
        name: variant.get(name, 0) - baseline.get(name, 0)
        for name in names
        if variant.get(name, 0) != baseline.get(name, 0)
    }
    return dict(sorted(changes.items(), key=lambda item: (-abs(item[1]), item[0])))


def _stability_summary(
    baseline: Sequence[TeamEvaluation], variant: Sequence[TeamEvaluation]
) -> dict[str, Any]:
    baseline_top10 = {team_key(evaluation) for evaluation in baseline[:10]}
    variant_top10 = {team_key(evaluation) for evaluation in variant[:10]}
    baseline_top50 = {team_key(evaluation) for evaluation in baseline[:50]}
    variant_top50 = {team_key(evaluation) for evaluation in variant[:50]}
    top50_intersection = baseline_top50 & variant_top50
    top50_union = baseline_top50 | variant_top50

    baseline_ranks = {
        team_key(evaluation): rank
        for rank, evaluation in enumerate(baseline, start=1)
    }
    variant_ranks = {
        team_key(evaluation): rank
        for rank, evaluation in enumerate(variant, start=1)
    }
    relevant_teams = baseline_top50 | variant_top50
    evaluation_by_key = {
        team_key(evaluation): evaluation for evaluation in (*baseline[:50], *variant[:50])
    }
    movements = sorted(
        (
            {
                "team": [
                    member.name for member in evaluation_by_key[key].members
                ],
                "baseline_rank": baseline_ranks[key],
                "variant_rank": variant_ranks[key],
                "movement": baseline_ranks[key] - variant_ranks[key],
            }
            for key in relevant_teams
        ),
        key=lambda item: (-abs(item["movement"]), item["variant_rank"]),
    )

    baseline_model = _model_summary(baseline)
    variant_model = _model_summary(variant)
    return {
        "top_10_overlap": len(baseline_top10 & variant_top10),
        "top_50_overlap": len(top50_intersection),
        "top_50_jaccard": len(top50_intersection) / len(top50_union),
        "frequency_changes": _frequency_changes(
            baseline_model["top_50_frequency"], variant_model["top_50_frequency"]
        ),
        "grouped_frequency_changes": _frequency_changes(
            baseline_model["top_50_frequency_grouped"],
            variant_model["top_50_frequency_grouped"],
        ),
        "largest_top50_movements": movements[:10],
    }


def run_sensitivity_analysis(
    entries: Sequence[RankingEntry],
    configs: Mapping[ScoringName, ScoringConfig] = SCORING_CONFIGS,
) -> tuple[dict[ScoringName, list[TeamEvaluation]], dict[str, Any]]:
    """Run the same exhaustive search once for each scoring configuration."""
    evaluations = {
        name: rank_teams(entries, scoring_config=config)
        for name, config in configs.items()
    }
    baseline = evaluations[ScoringName.BASELINE]
    models = {
        name.value: _model_summary(model_evaluations)
        for name, model_evaluations in evaluations.items()
    }
    stability = {
        name.value: _stability_summary(baseline, model_evaluations)
        for name, model_evaluations in evaluations.items()
    }
    return evaluations, {"models": models, "stability_vs_baseline": stability}


def write_sensitivity_outputs(
    output_directory: Path | str,
    evaluations: Mapping[ScoringName, Sequence[TeamEvaluation]],
    summary: Mapping[str, Any],
) -> tuple[Path, Path]:
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, model_evaluations in evaluations.items():
        write_top_teams(
            output_dir / f"top_teams_{name.value}.csv", model_evaluations, limit=50
        )

    csv_path = output_dir / "v1_1_comparison.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COMPARISON_FIELDS)
        writer.writeheader()
        for name in ScoringName:
            model = summary["models"][name.value]
            stability = summary["stability_vs_baseline"][name.value]
            top = model["top_10"][0]
            structure = model["structure"]
            source_rank = model["source_rank_top10"]
            writer.writerow(
                {
                    "scoring": name.value,
                    "top_team": "|".join(top["team"]),
                    "top_score": f"{top['total_score']:.6f}",
                    "steel_team_pct": f"{structure['steel_team_pct']:.6f}",
                    "flying_team_pct": f"{structure['flying_team_pct']:.6f}",
                    "steel_and_flying_team_pct": (
                        f"{structure['steel_and_flying_team_pct']:.6f}"
                    ),
                    "water_team_pct": f"{structure['water_team_pct']:.6f}",
                    "all_dual_type_team_pct": (
                        f"{structure['all_dual_type_team_pct']:.6f}"
                    ),
                    "zero_shared_weakness_teams": structure[
                        "zero_shared_weakness_teams"
                    ],
                    "mean_source_rank_top10": f"{source_rank['mean']:.6f}",
                    "median_source_rank_top10": source_rank["median"],
                    "worst_source_rank_top10": source_rank["worst_rank"],
                    "pvpoke_top3_optimizer_rank": model[
                        "pvpoke_top3_optimizer_rank"
                    ],
                    "baseline_top10_overlap": stability["top_10_overlap"],
                    "baseline_top50_overlap": stability["top_50_overlap"],
                    "baseline_top50_jaccard": f"{stability['top_50_jaccard']:.6f}",
                }
            )

    json_path = output_dir / "v1_1_summary.json"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")
    return csv_path, json_path
