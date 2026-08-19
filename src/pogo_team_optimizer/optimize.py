"""Command-line entry point for the optimization pipeline."""

import argparse
from collections.abc import Sequence

from pogo_team_optimizer.leagues import LeagueSlug, get_league


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.top < 3:
        raise SystemExit("--top must be at least 3")

    league = get_league(args.league)
    cp_label = f"CP {league.cp_cap}" if league.cp_cap is not None else "no CP cap"
    print(
        f"Scaffold ready: {league.display_name} ({cp_label}), "
        f"top {args.top} candidates."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
