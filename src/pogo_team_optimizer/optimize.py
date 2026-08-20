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
    readiness_by_instance,
    ready_now_candidates,
    team_buildability_reasons,
    team_power_up_gaps,
)
from pogo_team_optimizer.output import (
    write_inspection_priorities,
    write_inventory_diagnostics,
    write_scout_teams,
    write_top_teams,
    write_v2_top_teams,
)
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
from pogo_team_optimizer.readiness import (
    DEFAULT_READINESS_CONFIG,
    ReadinessConfig,
)
from pogo_team_optimizer.scout import (
    provisional_team_classification,
    rank_move_inspection_priorities,
)
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
        choices=[name.value for name in ScoringName] + ["v2", "v2.1", "v2.2"],
        default=ScoringName.BASELINE.value,
        help="scoring configuration to evaluate (default: baseline)",
    )
    parser.add_argument(
        "--inventory", type=Path, help="owned-instance inventory CSV (V2/V2.1/V2.2)"
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
        "--ready-threshold",
        type=float,
        default=DEFAULT_READINESS_CONFIG.ready_ratio_threshold,
        metavar="RATIO",
        help="ready-now CP/target-CP ratio for V2.2 (default: 0.95)",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="write full move-aware versus V1/V1.1 diagnostics",
    )
    parser.add_argument(
        "--scout",
        action="store_true",
        help="provisionally score unknown moves with PvPoke recommendations (V2.2)",
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
    try:
        readiness_config = ReadinessConfig(args.ready_threshold)
    except ValueError as error:
        parser.error(str(error))
    if args.inventory and args.scoring not in {"v2", "v2.1", "v2.2"}:
        parser.error("--inventory requires --scoring v2, v2.1, or v2.2")
    if args.diagnostics and args.scoring not in {"v2", "v2.1", "v2.2"}:
        parser.error("--diagnostics requires move-aware scoring")
    if args.compare_scoring and args.scoring in {"v2", "v2.1", "v2.2"}:
        parser.error("--compare-scoring is for V1/V1.1; use --diagnostics with V2")
    if args.scout and (args.scoring != "v2.2" or not args.inventory):
        parser.error("--scout requires --scoring v2.2 and --inventory")

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

    if args.scoring in {"v2", "v2.1", "v2.2"}:
        return _run_v2(
            args,
            parser,
            league,
            input_path,
            output_directory,
            readiness_config,
        )

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


def _run_v2(
    args,
    parser,
    league,
    input_path: Path,
    output_directory: Path,
    readiness_config: ReadinessConfig,
) -> int:
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
        theoretical = rank_v2_teams(theoretical_candidates, scoring=args.scoring)
    except (RankingParseError, MoveResolutionError, ValueError) as error:
        parser.error(str(error))

    inventory_evaluations = None
    ready_evaluations = []
    power_up_evaluations = []
    scout_evaluations = []
    inspection_priorities = []
    diagnostics = []
    if args.inventory:
        try:
            all_candidates, all_unresolved = resolve_ranking_entries(
                all_entries, game_master, species_ids
            )
            inventory_records = read_inventory(args.inventory)
            owned, diagnostics = inventory_candidates(
                inventory_records,
                all_candidates,
                game_master,
                league.cp_cap,
                readiness_config,
                scout_mode=args.scout,
            )
        except (InventoryError, MoveResolutionError, ValueError) as error:
            parser.error(str(error))
        if all_unresolved:
            print(f"Full-pool unresolved rows: {len(all_unresolved)}", file=sys.stderr)
        if len(owned) < 3:
            parser.error(f"庫存中只有 {len(owned)} 隻可評分候選，至少需要 3 隻")
        strict_owned = [candidate for candidate in owned if not candidate.moves_provisional]
        inventory_evaluations = (
            rank_v2_teams(strict_owned, scoring=args.scoring)
            if len(strict_owned) >= 3
            else []
        )
        if args.scoring == "v2.2":
            ready = ready_now_candidates(strict_owned, diagnostics)
            ready_evaluations = (
                rank_v2_teams(ready, scoring=args.scoring) if len(ready) >= 3 else []
            )
            power_up_evaluations = [
                evaluation
                for evaluation in inventory_evaluations
                if team_power_up_gaps(evaluation.members, diagnostics)
            ]
            if args.scout:
                scout_evaluations = [
                    evaluation
                    for evaluation in rank_v2_teams(owned, scoring=args.scoring)
                    if any(member.moves_provisional for member in evaluation.members)
                ]
                inspection_priorities = rank_move_inspection_priorities(
                    owned,
                    scout_evaluations,
                    inventory_records,
                    diagnostics,
                )

    if args.scoring == "v2.2" and args.inventory:
        return _write_and_report_v22_inventory(
            args,
            league,
            output_directory,
            theoretical,
            top_entries,
            theoretical_candidates,
            owned,
            diagnostics,
            ready_evaluations,
            power_up_evaluations,
            scout_evaluations,
            inspection_priorities,
        )

    evaluations = inventory_evaluations or theoretical
    version = args.scoring.replace(".", "_")
    default_name = f"top_teams_{version}{'_inventory' if args.inventory else ''}.csv"
    output_path = args.output or output_directory / default_name
    write_v2_top_teams(
        output_path,
        evaluations,
        limit=max(50, args.results),
        scoring_name=args.scoring,
    )
    if args.inventory:
        inventory_diagnostics_path = output_directory / "inventory_diagnostics.csv"
        write_inventory_diagnostics(inventory_diagnostics_path, diagnostics)
        print(f"Inventory diagnostics: {inventory_diagnostics_path}")
    if args.diagnostics:
        diagnostics_path = output_directory / "v2_diagnostics.json"
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        v2_for_diagnostics = (
            theoretical
            if args.scoring == "v2"
            else rank_v2_teams(theoretical_candidates, scoring="v2")
        )
        summary = build_v2_diagnostics(top_entries, v2_for_diagnostics)
        summary["requested_scoring"] = args.scoring
        with diagnostics_path.open("w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)
        print(f"Diagnostics: {diagnostics_path}")
    print(
        f"{league.display_name}: {args.scoring} theoretical evaluated "
        f"{len(theoretical):,} teams "
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
        print(f"Theoretical Top {min(args.results, 10)} buildability:")
        for team_rank, evaluation in enumerate(
            theoretical[: min(args.results, 10)], 1
        ):
            reasons = team_buildability_reasons(
                evaluation.members, owned, diagnostics
            )
            print(f"  #{team_rank}: {'; '.join(reasons)}")
        for diagnostic in diagnostics:
            print(
                f"inventory {diagnostic.instance_id}: {diagnostic.status.value} "
                f"— match={diagnostic.moveset_match or 'n/a'}; "
                f"actual={' / '.join(diagnostic.actual_moves) or 'n/a'}; "
                f"recommended={' / '.join(diagnostic.recommended_moves) or 'n/a'}; "
                f"quality={diagnostic.actual_move_quality!s} vs "
                f"{diagnostic.recommended_move_quality!s}; "
                f"delta={diagnostic.move_quality_delta!s}; {diagnostic.message}"
            )
    print(f"Results: {output_path}")
    print(f"Top {args.results}:")
    for rank, evaluation in enumerate(evaluations[: args.results], 1):
        names = " / ".join(member.name for member in evaluation.members)
        print(f"{rank:>2}. {names} | {evaluation.score.total_score:.4f}")
    return 0


def _write_and_report_v22_inventory(
    args,
    league,
    output_directory: Path,
    theoretical,
    top_entries,
    theoretical_candidates,
    owned,
    diagnostics,
    ready_evaluations,
    power_up_evaluations,
    scout_evaluations,
    inspection_priorities,
) -> int:
    assessments = readiness_by_instance(diagnostics)
    if args.output:
        ready_path = args.output
        power_path = args.output.with_name(f"{args.output.stem}_power_up{args.output.suffix}")
        theoretical_path = args.output.with_name(
            f"{args.output.stem}_theoretical{args.output.suffix}"
        )
    else:
        ready_path = output_directory / "top_teams_v2_2_ready.csv"
        power_path = output_directory / "top_teams_v2_2_power_up.csv"
        theoretical_path = output_directory / "top_teams_v2_2_theoretical.csv"
    limit = max(50, args.results)
    write_v2_top_teams(
        ready_path,
        ready_evaluations,
        limit,
        assessments,
        scoring_name="v2.2",
    )
    write_v2_top_teams(
        power_path,
        power_up_evaluations,
        limit,
        assessments,
        scoring_name="v2.2",
    )
    write_v2_top_teams(
        theoretical_path,
        theoretical,
        limit,
        scoring_name="v2.2",
    )
    diagnostics_path = output_directory / "inventory_diagnostics.csv"
    write_inventory_diagnostics(diagnostics_path, diagnostics)
    if args.scout:
        scout_path = output_directory / "inventory_scout_teams.csv"
        priority_path = output_directory / "inventory_move_check_priority.csv"
        write_scout_teams(scout_path, scout_evaluations, diagnostics, limit)
        write_inspection_priorities(priority_path, inspection_priorities)
    if args.diagnostics:
        v2_diagnostics_path = output_directory / "v2_diagnostics.json"
        summary = build_v2_diagnostics(
            top_entries,
            rank_v2_teams(theoretical_candidates, scoring="v2"),
        )
        summary["requested_scoring"] = "v2.2"
        with v2_diagnostics_path.open("w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)
        print(f"Diagnostics: {v2_diagnostics_path}")

    print(
        f"{league.display_name}: V2.2 readiness threshold="
        f"{args.ready_threshold:.1%}; CP ratio is a buildability heuristic, not IV simulation."
    )
    print("THEORETICAL:")
    _print_move_aware_teams(theoretical, args.results)
    print("READY NOW:")
    if ready_evaluations:
        _print_move_aware_teams(ready_evaluations, args.results)
    else:
        print("  none — fewer than three distinct ready-now species form a legal team")
    print("POWER-UP NEEDED:")
    if power_up_evaluations:
        for rank, evaluation in enumerate(power_up_evaluations[: args.results], 1):
            names = " / ".join(member.name for member in evaluation.members)
            gaps = ", ".join(
                f"{name} CP {actual}→{target} (+{gap})"
                for name, actual, target, gap in team_power_up_gaps(
                    evaluation.members, diagnostics
                )
            )
            print(
                f"  {rank:>2}. {names} | {evaluation.score.total_score:.4f} "
                f"| {gaps}"
            )
    else:
        print("  none")
    if args.scout:
        print("TOP PROVISIONAL TEAMS:")
        if scout_evaluations:
            for rank, evaluation in enumerate(scout_evaluations[: args.results], 1):
                names = " / ".join(member.name for member in evaluation.members)
                assumed = ", ".join(
                    member.instance_id or member.name
                    for member in evaluation.members
                    if member.moves_provisional
                )
                classification = provisional_team_classification(
                    evaluation.members, diagnostics
                ).value
                print(
                    f"  {rank:>2}. {names} | {evaluation.score.total_score:.4f} "
                    f"| {classification} | PROVISIONAL assumed recommended: {assumed}"
                )
        else:
            print("  none")
        print("TOP POKÉMON TO CHECK NEXT:")
        for rank, item in enumerate(inspection_priorities[:15], 1):
            print(
                f"  {rank:>2}. {item.pokemon_name} [{item.instance_id}] "
                f"CP {item.cp} | priority={item.inspection_priority:.4f} | "
                f"top-team count={item.top_team_frequency}, "
                f"best provisional rank={item.best_provisional_team_rank or 'n/a'}"
            )
        print(f"Scout teams: {scout_path}")
        print(f"Move-check priority: {priority_path}")
    print(f"Ready-now results: {ready_path}")
    print(f"Power-up-needed results: {power_path}")
    print(f"Theoretical results: {theoretical_path}")
    print(f"Inventory diagnostics: {diagnostics_path}")
    print(f"Theoretical Top {min(args.results, 10)} buildability:")
    for team_rank, evaluation in enumerate(theoretical[: min(args.results, 10)], 1):
        reasons = team_buildability_reasons(evaluation.members, owned, diagnostics)
        print(f"  #{team_rank}: {'; '.join(reasons)}")
    return 0


def _print_move_aware_teams(evaluations, limit: int) -> None:
    for rank, evaluation in enumerate(evaluations[:limit], 1):
        names = " / ".join(member.name for member in evaluation.members)
        print(f"  {rank:>2}. {names} | {evaluation.score.total_score:.4f}")


if __name__ == "__main__":
    raise SystemExit(main())
