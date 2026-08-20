"""Result serialization for V1 optimization runs."""

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

from pogo_team_optimizer.search import TeamEvaluation
from pogo_team_optimizer.search_v2 import V2TeamEvaluation
from pogo_team_optimizer.inventory import InventoryDiagnostic
from pogo_team_optimizer.readiness import ReadinessAssessment


RESULT_FIELDS = (
    "overall_rank",
    "pokemon_1",
    "pokemon_2",
    "pokemon_3",
    "total_score",
    "ranking_quality",
    "shared_weakness_penalty",
    "severe_weakness_penalty",
    "resistance_coverage",
    "teammate_weakness_coverage",
    "defensive_diversity",
    "shared_weaknesses",
    "resistance_coverage_summary",
)


def write_top_teams(
    path: Path | str, evaluations: Sequence[TeamEvaluation], limit: int = 50
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for overall_rank, evaluation in enumerate(evaluations[:limit], start=1):
            breakdown = evaluation.score
            writer.writerow(
                {
                    "overall_rank": overall_rank,
                    "pokemon_1": evaluation.members[0].name,
                    "pokemon_2": evaluation.members[1].name,
                    "pokemon_3": evaluation.members[2].name,
                    "total_score": f"{breakdown.total_score:.4f}",
                    "ranking_quality": f"{breakdown.ranking_quality:.6f}",
                    "shared_weakness_penalty": f"{breakdown.shared_weakness_penalty:.6f}",
                    "severe_weakness_penalty": f"{breakdown.severe_weakness_penalty:.6f}",
                    "resistance_coverage": f"{breakdown.resistance_coverage:.6f}",
                    "teammate_weakness_coverage": (
                        f"{breakdown.teammate_weakness_coverage:.6f}"
                    ),
                    "defensive_diversity": f"{breakdown.defensive_diversity:.6f}",
                    "shared_weaknesses": "|".join(
                        f"{pokemon_type}:{count}"
                        for pokemon_type, count in evaluation.shared_weaknesses
                    ),
                    "resistance_coverage_summary": "|".join(
                        evaluation.resistance_coverage
                    ),
                }
            )


V2_RESULT_FIELDS = (
    "scoring",
    "overall_rank", "pokemon_1", "pokemon_2", "pokemon_3", "instance_1",
    "instance_2", "instance_3", "total_score", "defensive_v1_score",
    "unique_offensive_type_coverage", "super_effective_coverage",
    "charged_move_coverage", "fast_move_coverage", "stab_move_availability",
    "offensive_redundancy", "defensive_offensive_balance",
    "super_effective_types", "charged_super_effective_types",
    "fast_super_effective_types",
    "actual_move_quality", "recommended_move_quality", "move_quality_delta",
    "move_quality_adjustment",
    "actual_cp_1", "target_cp_1", "cp_gap_1", "readiness_ratio_1",
    "readiness_status_1", "target_cp_source_1",
    "actual_cp_2", "target_cp_2", "cp_gap_2", "readiness_ratio_2",
    "readiness_status_2", "target_cp_source_2",
    "actual_cp_3", "target_cp_3", "cp_gap_3", "readiness_ratio_3",
    "readiness_status_3", "target_cp_source_3",
)


def write_v2_top_teams(
    path: Path | str,
    evaluations: Sequence[V2TeamEvaluation],
    limit: int = 50,
    readiness: Mapping[str, ReadinessAssessment] | None = None,
    scoring_name: str | None = None,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=V2_RESULT_FIELDS)
        writer.writeheader()
        for overall_rank, evaluation in enumerate(evaluations[:limit], start=1):
            raw_score = evaluation.score
            score = getattr(raw_score, "v2_score", raw_score)
            has_move_quality = hasattr(raw_score, "v2_score")
            scoring = scoring_name or (
                "v2.1" if has_move_quality else "v2"
            )
            members = evaluation.members
            row = {
                "overall_rank": overall_rank,
                "scoring": scoring,
                **{f"pokemon_{i}": member.name for i, member in enumerate(members, 1)},
                **{f"instance_{i}": member.instance_id or "" for i, member in enumerate(members, 1)},
                "total_score": f"{raw_score.total_score:.4f}",
                "defensive_v1_score": f"{score.defensive_score.total_score:.4f}",
                "unique_offensive_type_coverage": f"{score.unique_offensive_type_coverage:.6f}",
                "super_effective_coverage": f"{score.super_effective_coverage:.6f}",
                "charged_move_coverage": f"{score.charged_move_coverage:.6f}",
                "fast_move_coverage": f"{score.fast_move_coverage:.6f}",
                "stab_move_availability": f"{score.stab_move_availability:.6f}",
                "offensive_redundancy": f"{score.offensive_redundancy:.6f}",
                "defensive_offensive_balance": f"{score.defensive_offensive_balance:.6f}",
                "super_effective_types": "|".join(v.value for v in score.all_move_summary.super_effective),
                "charged_super_effective_types": "|".join(v.value for v in score.charged_move_summary.super_effective),
                "fast_super_effective_types": "|".join(v.value for v in score.fast_move_summary.super_effective),
                "actual_move_quality": (
                    f"{raw_score.actual_move_quality:.6f}"
                    if has_move_quality else ""
                ),
                "recommended_move_quality": (
                    f"{raw_score.recommended_move_quality:.6f}"
                    if has_move_quality else ""
                ),
                "move_quality_delta": (
                    f"{raw_score.move_quality_delta:.6f}"
                    if has_move_quality else ""
                ),
                "move_quality_adjustment": (
                    f"{raw_score.move_quality_adjustment:.6f}"
                    if has_move_quality else ""
                ),
            }
            for index, member in enumerate(members, 1):
                assessment = (
                    readiness.get(member.instance_id)
                    if readiness is not None and member.instance_id is not None
                    else None
                )
                row.update(
                    {
                        f"actual_cp_{index}": assessment.actual_cp if assessment else "",
                        f"target_cp_{index}": assessment.target_cp if assessment else "",
                        f"cp_gap_{index}": assessment.cp_gap if assessment else "",
                        f"readiness_ratio_{index}": (
                            f"{assessment.readiness_ratio:.6f}" if assessment else ""
                        ),
                        f"readiness_status_{index}": (
                            assessment.status.value if assessment else ""
                        ),
                        f"target_cp_source_{index}": (
                            assessment.target_source.value if assessment else ""
                        ),
                    }
                )
            writer.writerow(row)


INVENTORY_DIAGNOSTIC_FIELDS = (
    "instance_id", "status", "species_id", "actual_moves",
    "recommended_moves", "moveset_match", "actual_move_quality",
    "recommended_move_quality", "move_quality_delta",
    "second_charged_move_missing", "message",
    "actual_cp", "target_cp", "cp_gap", "readiness_ratio",
    "readiness_status", "target_cp_source",
)


def write_inventory_diagnostics(
    path: Path | str, diagnostics: Sequence[InventoryDiagnostic]
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INVENTORY_DIAGNOSTIC_FIELDS)
        writer.writeheader()
        for item in diagnostics:
            writer.writerow(
                {
                    "instance_id": item.instance_id,
                    "status": item.status.value,
                    "species_id": item.species_id or "",
                    "actual_moves": "|".join(item.actual_moves),
                    "recommended_moves": "|".join(item.recommended_moves),
                    "moveset_match": item.moveset_match or "",
                    "actual_move_quality": (
                        f"{item.actual_move_quality:.6f}"
                        if item.actual_move_quality is not None else ""
                    ),
                    "recommended_move_quality": (
                        f"{item.recommended_move_quality:.6f}"
                        if item.recommended_move_quality is not None else ""
                    ),
                    "move_quality_delta": (
                        f"{item.move_quality_delta:.6f}"
                        if item.move_quality_delta is not None else ""
                    ),
                    "second_charged_move_missing": item.second_charged_move_missing,
                    "message": item.message,
                    "actual_cp": item.readiness.actual_cp if item.readiness else "",
                    "target_cp": item.readiness.target_cp if item.readiness else "",
                    "cp_gap": item.readiness.cp_gap if item.readiness else "",
                    "readiness_ratio": (
                        f"{item.readiness.readiness_ratio:.6f}"
                        if item.readiness else ""
                    ),
                    "readiness_status": (
                        item.readiness.status.value if item.readiness else ""
                    ),
                    "target_cp_source": (
                        item.readiness.target_source.value if item.readiness else ""
                    ),
                }
            )
