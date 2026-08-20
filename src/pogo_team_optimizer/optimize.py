"""Command-line entry point for backward-compatible V1/V1.1 and V2 pipelines."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pogo_team_optimizer.leagues import LeagueSlug, get_league
from pogo_team_optimizer.inventory import (
    InventoryError,
    inventory_candidates,
    read_inventory,
)
from pogo_team_optimizer.output import write_top_teams, write_v2_top_teams
from pogo_team_optimizer.parsing import (
    MoveResolutionError,
    RankingParseError,
    read_game_master,
    read_rankings,
    read_rankings_json,
    resolve_ranking_entries,
    select_top,
)
from pogo_team_optimizer.scoring import ScoringName, get_scoring_config
from pogo_team_optimizer.search import candidate_team_count, rank_teams
from pogo_team_optimizer.search_v2 import rank_v2_teams
from pogo_team_optimizer.v2_diagnostics import build_v2_diagnostics
from pogo_team_optimizer.sensitivity import (
    run_sensitivity_analysis,
    write_sensitivity_outputs,
)


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
    parser.add_argument(
        "--scoring",
        choices=[name.value for name in ScoringName] + ["v2"],
        default=ScoringName.BASELINE.value,
        help="scoring configuration to evaluate (default: baseline)",
    )
    parser.add_argument(
        "--inventory", type=Path, help="owned-instance inventory CSV (V2 only)"
    )
    parser.add_argument(
        "--gamemaster",
        type=Path,
        default=Path("data/cache/gamemaster.json"),
        help="PvPoke GameMaster JSON cache path",
    )
    parser.add_argument(
        "--aliases", type=Path, help="optional localized Pokémon/move alias JSON"
    )
    parser.add_argument(
        "--results",
        type=int,
        default=10,
        metavar="N",
        help="number of fallback teams to display (default: 10)",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="write full V2 versus V1/V1.1 diagnostics (V2 only)",
    )
    parser.add_argument(
        "--compare-scoring",
        action="store_true",
        help="run all V1/V1.1 scoring configurations and write comparison outputs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.top < 3:
        parser.error("--top must be at least 3")
    if args.results < 1:
        parser.error("--results must be at least 1")
    if args.inventory and args.scoring != "v2":
        parser.error("--inventory requires --scoring v2")
    if args.diagnostics and args.scoring != "v2":
        parser.error("--diagnostics requires --scoring v2")
    if args.compare_scoring and args.scoring == "v2":
        parser.error("--compare-scoring is for V1/V1.1; use --diagnostics with V2")

    league = get_league(args.league)
    input_path = args.input or (
        Path("data") / league.directory_name / league.ranking_filename
    )
    output_directory = Path("results") / league.directory_name
    if args.compare_scoring and args.output is not None:
        parser.error("--output cannot be combined with --compare-scoring")

    if not input_path.is_file():
        parser.error(
            f"找不到 {league.display_name} 排名 CSV：{input_path}。"
            f"請將 PvPoke 排名匯出檔放到這個路徑，或使用 --input 指定檔案。"
        )

    if args.scoring == "v2":
        return _run_v2(args, parser, league, input_path, output_directory)

    try:
        entries = select_top(read_rankings(input_path), args.top)
    except (RankingParseError, ValueError) as error:
        parser.error(str(error))

    if args.compare_scoring:
        evaluations_by_name, summary = run_sensitivity_analysis(entries)
        comparison_path, summary_path = write_sensitivity_outputs(
            output_directory, evaluations_by_name, summary
        )
        print(
            f"{league.display_name}: evaluated {candidate_team_count(args.top):,} "
            f"unique teams under {len(evaluations_by_name)} scoring configurations."
        )
        for name, model_evaluations in evaluations_by_name.items():
            top_team = " / ".join(
                member.name for member in model_evaluations[0].members
            )
            print(
                f"{name.value}: {top_team} | "
                f"{model_evaluations[0].score.total_score:.4f}"
            )
        print(f"Comparison: {comparison_path}")
        print(f"Summary: {summary_path}")
        return 0

    scoring_config = get_scoring_config(args.scoring)
    default_filename = (
        "top_teams.csv"
        if scoring_config.name is ScoringName.BASELINE
        else f"top_teams_{scoring_config.name.value}.csv"
    )
    output_path = args.output or output_directory / default_filename
    evaluations = rank_teams(entries, scoring_config=scoring_config)
    write_top_teams(output_path, evaluations, limit=50)

    print(
        f"{league.display_name}: evaluated {len(evaluations):,} teams "
        f"from the top {args.top} Pokémon "
        f"(expected {candidate_team_count(args.top):,}); "
        f"scoring={scoring_config.name.value}."
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


def _run_v2(args, parser, league, input_path: Path, output_directory: Path) -> int:
    if not args.gamemaster.is_file():
        parser.error(
            f"找不到 PvPoke GameMaster：{args.gamemaster}。請下載 gamemaster.json 或用 --gamemaster 指定。"
        )
    try:
        game_master = read_game_master(args.gamemaster, args.aliases)
        if input_path.suffix.casefold() == ".json":
            all_entries, species_ids = read_rankings_json(input_path, game_master)
        else:
            all_entries, species_ids = read_rankings(input_path), None
        top_entries = select_top(all_entries, args.top)
        top_species_ids = species_ids[: args.top] if species_ids else None
        theoretical_candidates, unresolved = resolve_ranking_entries(
            top_entries, game_master, top_species_ids
        )
        if unresolved:
            print("Unresolved ranking rows:", file=sys.stderr)
            for message in unresolved:
                print(f"- {message}", file=sys.stderr)
        if len(theoretical_candidates) < 3:
            parser.error("解析後不足三隻可評分的寶可夢")
        theoretical = rank_v2_teams(theoretical_candidates)
    except (RankingParseError, MoveResolutionError, ValueError) as error:
        parser.error(str(error))

    inventory_evaluations = None
    diagnostics = []
    if args.inventory:
        try:
            all_candidates, all_unresolved = resolve_ranking_entries(
                all_entries, game_master, species_ids
            )
            owned, diagnostics = inventory_candidates(
                read_inventory(args.inventory),
                all_candidates,
                game_master,
                league.cp_cap,
            )
        except (InventoryError, MoveResolutionError, ValueError) as error:
            parser.error(str(error))
        if all_unresolved:
            print(f"Full-pool unresolved rows: {len(all_unresolved)}", file=sys.stderr)
        if len(owned) < 3:
            parser.error(f"庫存中只有 {len(owned)} 隻可評分候選，至少需要 3 隻")
        inventory_evaluations = rank_v2_teams(owned)

    evaluations = inventory_evaluations or theoretical
    default_name = (
        "top_teams_v2_inventory.csv" if args.inventory else "top_teams_v2.csv"
    )
    output_path = args.output or output_directory / default_name
    write_v2_top_teams(output_path, evaluations, limit=max(50, args.results))
    if args.diagnostics:
        diagnostics_path = output_directory / "v2_diagnostics.json"
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        summary = build_v2_diagnostics(top_entries, theoretical)
        with diagnostics_path.open("w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)
        print(f"Diagnostics: {diagnostics_path}")
    print(
        f"{league.display_name}: V2 theoretical evaluated {len(theoretical):,} teams "
        f"from {len(theoretical_candidates)} resolved top-{args.top} candidates."
    )
    theoretical_names = " / ".join(member.name for member in theoretical[0].members)
    print(f"Best theoretical: {theoretical_names} | {theoretical[0].score.total_score:.4f}")
    if inventory_evaluations is not None:
        owned_species = {candidate.species_id for candidate in owned}
        missing = [
            member.name
            for member in theoretical[0].members
            if member.species_id not in owned_species
        ]
        best = inventory_evaluations[0]
        buildability = "buildable" if not missing else "missing " + ", ".join(missing)
        print(f"Theoretical buildability: {buildability}")
        print(
            f"Best inventory-buildable: {' / '.join(member.name for member in best.members)} "
            f"| {best.score.total_score:.4f} | score gap {theoretical[0].score.total_score - best.score.total_score:.4f} "
            f"| ranking pool depth #{max(member.rank for member in best.members)}"
        )
        for diagnostic in diagnostics:
            print(
                f"inventory {diagnostic.instance_id}: {diagnostic.status.value} "
                f"— {diagnostic.message}"
            )
    print(f"Results: {output_path}")
    print(f"Top {args.results}:")
    for rank, evaluation in enumerate(evaluations[: args.results], 1):
        names = " / ".join(member.name for member in evaluation.members)
        print(f"{rank:>2}. {names} | {evaluation.score.total_score:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
