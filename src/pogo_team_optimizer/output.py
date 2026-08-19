"""Result serialization for V1 optimization runs."""

import csv
from collections.abc import Sequence
from pathlib import Path

from pogo_team_optimizer.search import TeamEvaluation


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
