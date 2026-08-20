"""CLI for focused V3 PvPoke matchup validation."""

from __future__ import annotations

import argparse
from pathlib import Path

from pogo_team_optimizer.battle.pvpoke import (
    PvPokeBridgeError,
    PvPokeEngine,
    VENDORED_PVPOKE_COMMIT,
)
from pogo_team_optimizer.battle.v3 import (
    compare_movesets,
    load_experiment,
    load_meta_opponents,
    simulate_experiment,
    summarize_moveset,
    summarize_team,
    write_matchups,
    write_summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate focused Great League teams with PvPoke 1v1 simulations."
    )
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument(
        "--rankings", type=Path, default=Path("data/cache/rankings-1500.json")
    )
    parser.add_argument(
        "--gamemaster", type=Path, default=Path("data/cache/gamemaster.json")
    )
    parser.add_argument(
        "--meta-sizes", type=int, nargs="+", default=[50], metavar="N"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/great_league")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    sizes = sorted(set(args.meta_sizes))
    if not sizes or sizes[0] < 1:
        parser.error("--meta-sizes values must be positive")
    try:
        experiment = load_experiment(args.experiment)
        opponents = load_meta_opponents(args.rankings, sizes[-1])
        engine = PvPokeEngine(args.gamemaster)
        records = simulate_experiment(engine, experiment, opponents)
    except (OSError, ValueError, KeyError, PvPokeBridgeError) as error:
        parser.error(str(error))

    print(
        f"PvPoke engine {VENDORED_PVPOKE_COMMIT[:12]}: "
        f"simulated {len(records):,} equal-state matchups."
    )
    for size in sizes:
        selected = [item for item in records if item.opponent_rank <= size]
        movesets = [
            summarize_moveset(candidate_id, moveset, selected)
            for candidate_id, moveset in experiment.variants.items()
        ]
        teams = [
            summarize_team(team_id, members, selected)
            for team_id, members in experiment.teams.items()
        ]
        comparisons = [
            compare_movesets(name, baseline, variant, selected)
            for name, baseline, variant in experiment.comparisons
        ]
        matchup_path = args.output_dir / f"v3_matchups_top{size}.csv"
        summary_path = args.output_dir / f"v3_summary_top{size}.json"
        write_matchups(matchup_path, selected)
        write_summary(
            summary_path,
            meta_size=size,
            movesets=movesets,
            teams=teams,
            comparisons=comparisons,
        )
        print(f"TOP {size} META")
        for team in sorted(teams, key=lambda item: (-item.robustness_score, item.team_id)):
            print(
                f"  {team.team_id}: robustness={team.robustness_score:.2f}; "
                f"coverage={team.coverage_rate:.1%}; avg rating={team.average_rating:.1f}; "
                f"hard counters={len(team.shared_hard_counters)}"
            )
        print(f"  Matchups: {matchup_path}")
        print(f"  Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
