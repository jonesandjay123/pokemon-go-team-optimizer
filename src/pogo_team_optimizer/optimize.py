"""Command-line entry point for the V1 optimization pipeline."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from pogo_team_optimizer.leagues import LeagueSlug, get_league
from pogo_team_optimizer.output import write_top_teams
from pogo_team_optimizer.parsing import RankingParseError, read_rankings, select_top
from pogo_team_optimizer.search import candidate_team_count, rank_teams


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimize a three-Pokémon PvP team for a selected league."
    )
    parser.add_argument(
        "--league",
        choices=[league.value for league in LeagueSlug],
        default=LeagueSlug.GREAT.value,
        help="league to evaluate (default: great)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        metavar="N",
        help="number of ranked Pokémon in the candidate pool (default: 50)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="override the league's local ranking CSV path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="override the output top_teams.csv path",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.top < 3:
        parser.error("--top must be at least 3")

    league = get_league(args.league)
    input_path = args.input or (
        Path("data") / league.directory_name / league.ranking_filename
    )
    output_path = args.output or (
        Path("results") / league.directory_name / "top_teams.csv"
    )

    if not input_path.is_file():
        parser.error(
            f"找不到 {league.display_name} 排名 CSV：{input_path}。"
            f"請將 PvPoke 排名匯出檔放到這個路徑，或使用 --input 指定檔案。"
        )

    try:
        entries = select_top(read_rankings(input_path), args.top)
    except (RankingParseError, ValueError) as error:
        parser.error(str(error))

    evaluations = rank_teams(entries)
    write_top_teams(output_path, evaluations, limit=50)

    print(
        f"{league.display_name}: evaluated {len(evaluations):,} teams "
        f"from the top {args.top} Pokémon "
        f"(expected {candidate_team_count(args.top):,})."
    )
    print(f"Results: {output_path}")
    print("Top 10:")
    for rank, evaluation in enumerate(evaluations[:10], start=1):
        names = " / ".join(member.name for member in evaluation.members)
        weaknesses = ", ".join(
            f"{pokemon_type}({count})"
            for pokemon_type, count in evaluation.shared_weaknesses
        ) or "none"
        print(
            f"{rank:>2}. {names} | {evaluation.score.total_score:.4f} "
            f"| shared weaknesses: {weaknesses}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
