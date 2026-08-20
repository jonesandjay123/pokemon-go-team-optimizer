"""V3 matchup summaries built exclusively from PvPoke battle results."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Final, Mapping, Sequence

from pogo_team_optimizer.battle.pvpoke import (
    BattleMatchup,
    BattleResult,
    Moveset,
    PvPokeEngine,
    VENDORED_PVPOKE_COMMIT,
)


SHIELD_SCENARIOS: Final = (0, 1, 2)
ROBUSTNESS_COVERAGE_WEIGHT: Final = 0.60
ROBUSTNESS_DEPTH_WEIGHT: Final = 0.20
ROBUSTNESS_RATING_WEIGHT: Final = 0.20


@dataclass(frozen=True, slots=True)
class MetaOpponent:
    rank: int
    name: str
    moveset: Moveset


@dataclass(frozen=True, slots=True)
class MatchupRecord:
    candidate_id: str
    opponent_rank: int
    opponent_name: str
    opponent_id: str
    shields: int
    result: BattleResult


@dataclass(frozen=True, slots=True)
class ShieldPerformance:
    shields: int
    win_rate: float
    average_rating: float
    covered_opponents: int
    zero_member_wins: int
    exactly_one_member_win: int
    two_or_more_member_wins: int


@dataclass(frozen=True, slots=True)
class MovesetSummary:
    candidate_id: str
    species_id: str
    label: str
    wins: int
    losses: int
    ties: int
    win_rate: float
    average_rating: float
    shield_performance: tuple[ShieldPerformance, ...]
    worst_opponent: str
    worst_opponent_rank: int
    worst_shields: int
    worst_rating: int


@dataclass(frozen=True, slots=True)
class TeamSummary:
    team_id: str
    members: tuple[str, str, str]
    meta_size: int
    scenario_cells: int
    covered_opponents: int
    coverage_rate: float
    zero_member_wins: int
    exactly_one_member_win: int
    two_or_more_member_wins: int
    depth_rate: float
    average_rating: float
    robustness_score: float
    shared_hard_counters: tuple[str, ...]
    worst_opponent: str
    worst_opponent_rank: int
    worst_shields: int
    worst_best_member_rating: int
    shield_performance: tuple[ShieldPerformance, ...]
    likely_lead: str
    likely_safe_swap: str
    likely_closer: str


@dataclass(frozen=True, slots=True)
class MatchupComparison:
    name: str
    baseline: str
    variant: str
    average_rating_delta: float
    win_rate_delta: float
    wins_gained: tuple[str, ...]
    wins_lost: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Experiment:
    variants: Mapping[str, Moveset]
    teams: Mapping[str, tuple[str, str, str]]
    comparisons: tuple[tuple[str, str, str], ...]


def load_experiment(path: Path | str) -> Experiment:
    with Path(path).open(encoding="utf-8") as file:
        raw = json.load(file)
    variants = {
        variant_id: Moveset(
            value["species_id"],
            value["fast_move"],
            tuple(value["charged_moves"]),
            value.get("label", variant_id),
        )
        for variant_id, value in raw["variants"].items()
    }
    for variant_id in variants:
        if "|" in variant_id:
            raise ValueError("variant IDs cannot contain '|'")
    teams: dict[str, tuple[str, str, str]] = {}
    for team_id, members in raw.get("teams", {}).items():
        if len(members) != 3 or len(set(members)) != 3:
            raise ValueError(f"team {team_id!r} must contain three distinct variants")
        unknown = set(members) - set(variants)
        if unknown:
            raise ValueError(f"team {team_id!r} references unknown variants: {sorted(unknown)}")
        teams[team_id] = tuple(members)
    comparisons = tuple(
        (item["name"], item["baseline"], item["variant"])
        for item in raw.get("comparisons", [])
    )
    for name, baseline, variant in comparisons:
        if baseline not in variants or variant not in variants:
            raise ValueError(f"comparison {name!r} references an unknown variant")
    return Experiment(variants, teams, comparisons)


def load_meta_opponents(path: Path | str, limit: int) -> list[MetaOpponent]:
    if limit < 1:
        raise ValueError("meta limit must be positive")
    with Path(path).open(encoding="utf-8") as file:
        raw = json.load(file)
    opponents: list[MetaOpponent] = []
    for rank, item in enumerate(raw[:limit], 1):
        moves = tuple(item["moveset"])
        if not 2 <= len(moves) <= 3:
            raise ValueError(f"ranking #{rank} has an invalid moveset: {moves}")
        opponents.append(
            MetaOpponent(
                rank,
                item.get("speciesName", item["speciesId"]),
                Moveset(item["speciesId"], moves[0], moves[1:], "PvPoke recommended"),
            )
        )
    if len(opponents) != limit:
        raise ValueError(f"ranking input contains only {len(opponents)} rows; requested {limit}")
    return opponents


def simulate_experiment(
    engine: PvPokeEngine,
    experiment: Experiment,
    opponents: Sequence[MetaOpponent],
) -> list[MatchupRecord]:
    requests: list[BattleMatchup] = []
    metadata: dict[str, tuple[str, MetaOpponent]] = {}
    for candidate_id, candidate in experiment.variants.items():
        for opponent in opponents:
            for shields in SHIELD_SCENARIOS:
                request_id = f"{candidate_id}|{opponent.rank}|{shields}"
                requests.append(
                    BattleMatchup(request_id, candidate, opponent.moveset, shields)
                )
                metadata[request_id] = candidate_id, opponent
    output: list[MatchupRecord] = []
    for result in engine.simulate(requests):
        candidate_id, opponent = metadata[result.request_id]
        output.append(
            MatchupRecord(
                candidate_id,
                opponent.rank,
                opponent.name,
                opponent.moveset.species_id,
                result.shields,
                result,
            )
        )
    output.sort(key=lambda item: (item.candidate_id, item.opponent_rank, item.shields))
    return output


def _shield_performance(
    records: Sequence[MatchupRecord], shields: int
) -> ShieldPerformance:
    selected = [item for item in records if item.shields == shields]
    wins = sum(item.result.candidate_rating > 500 for item in selected)
    return ShieldPerformance(
        shields=shields,
        win_rate=wins / len(selected) if selected else 0,
        average_rating=fmean(item.result.candidate_rating for item in selected)
        if selected else 0,
        covered_opponents=wins,
        zero_member_wins=len(selected) - wins,
        exactly_one_member_win=wins,
        two_or_more_member_wins=0,
    )


def summarize_moveset(
    candidate_id: str,
    moveset: Moveset,
    records: Sequence[MatchupRecord],
) -> MovesetSummary:
    selected = [item for item in records if item.candidate_id == candidate_id]
    if not selected:
        raise ValueError(f"no matchup records for {candidate_id}")
    wins = sum(item.result.candidate_rating > 500 for item in selected)
    losses = sum(item.result.candidate_rating < 500 for item in selected)
    ties = len(selected) - wins - losses
    worst = min(
        selected,
        key=lambda item: (
            item.result.candidate_rating,
            item.opponent_rank,
            item.shields,
        ),
    )
    return MovesetSummary(
        candidate_id,
        moveset.species_id,
        moveset.label or candidate_id,
        wins,
        losses,
        ties,
        wins / len(selected),
        fmean(item.result.candidate_rating for item in selected),
        tuple(_shield_performance(selected, shields) for shields in SHIELD_SCENARIOS),
        worst.opponent_name,
        worst.opponent_rank,
        worst.shields,
        worst.result.candidate_rating,
    )


def _team_shield_performance(
    cells: Sequence[tuple[tuple[int, str, int], Sequence[MatchupRecord]]],
    shields: int,
) -> ShieldPerformance:
    selected = [cell for cell in cells if cell[0][2] == shields]
    winner_counts = [
        sum(item.result.candidate_rating > 500 for item in member_records)
        for _, member_records in selected
    ]
    ratings = [
        item.result.candidate_rating
        for _, member_records in selected
        for item in member_records
    ]
    return ShieldPerformance(
        shields,
        sum(count > 0 for count in winner_counts) / len(selected),
        fmean(ratings),
        sum(count > 0 for count in winner_counts),
        sum(count == 0 for count in winner_counts),
        sum(count == 1 for count in winner_counts),
        sum(count >= 2 for count in winner_counts),
    )


def summarize_team(
    team_id: str,
    members: tuple[str, str, str],
    records: Sequence[MatchupRecord],
) -> TeamSummary:
    by_cell: defaultdict[tuple[int, str, int], list[MatchupRecord]] = defaultdict(list)
    for item in records:
        if item.candidate_id in members:
            by_cell[(item.opponent_rank, item.opponent_name, item.shields)].append(item)
    cells = sorted(by_cell.items())
    if not cells or any(len(member_records) != 3 for _, member_records in cells):
        raise ValueError(f"incomplete matchup matrix for team {team_id}")
    winner_counts = [
        sum(item.result.candidate_rating > 500 for item in member_records)
        for _, member_records in cells
    ]
    covered = sum(count > 0 for count in winner_counts)
    zero = sum(count == 0 for count in winner_counts)
    one = sum(count == 1 for count in winner_counts)
    deep = sum(count >= 2 for count in winner_counts)
    coverage_rate = covered / len(cells)
    depth_rate = fmean(min(count, 2) / 2 for count in winner_counts)
    average_rating = fmean(
        item.result.candidate_rating
        for _, member_records in cells
        for item in member_records
    )
    robustness = 100 * (
        ROBUSTNESS_COVERAGE_WEIGHT * coverage_rate
        + ROBUSTNESS_DEPTH_WEIGHT * depth_rate
        + ROBUSTNESS_RATING_WEIGHT * (average_rating / 1000)
    )
    hard_counters: list[str] = []
    opponent_names = sorted({(rank, name) for rank, name, _ in by_cell})
    for rank, name in opponent_names:
        relevant = [
            member_records
            for (cell_rank, _, _), member_records in cells
            if cell_rank == rank
        ]
        if all(
            not any(item.result.candidate_rating > 500 for item in member_records)
            for member_records in relevant
        ):
            hard_counters.append(name)
    worst_key, worst_records = min(
        cells,
        key=lambda cell: (
            max(item.result.candidate_rating for item in cell[1]),
            cell[0][0],
            cell[0][2],
        ),
    )
    member_records: defaultdict[str, list[MatchupRecord]] = defaultdict(list)
    for _, items in cells:
        for item in items:
            member_records[item.candidate_id].append(item)

    def average(member: str, shields: int) -> float:
        chosen = [item for item in member_records[member] if item.shields == shields]
        return fmean(item.result.candidate_rating for item in chosen)

    def floor_rating(member: str, shields: int) -> int:
        chosen = [item for item in member_records[member] if item.shields == shields]
        return min(item.result.candidate_rating for item in chosen)

    likely_lead = max(members, key=lambda member: (average(member, 2), member))
    likely_closer = max(members, key=lambda member: (average(member, 0), member))
    likely_safe_swap = max(
        members,
        key=lambda member: (floor_rating(member, 1), average(member, 1), member),
    )
    return TeamSummary(
        team_id,
        members,
        len(opponent_names),
        len(cells),
        covered,
        coverage_rate,
        zero,
        one,
        deep,
        depth_rate,
        average_rating,
        robustness,
        tuple(hard_counters),
        worst_key[1],
        worst_key[0],
        worst_key[2],
        max(item.result.candidate_rating for item in worst_records),
        tuple(_team_shield_performance(cells, shields) for shields in SHIELD_SCENARIOS),
        likely_lead,
        likely_safe_swap,
        likely_closer,
    )


def compare_movesets(
    name: str,
    baseline: str,
    variant: str,
    records: Sequence[MatchupRecord],
) -> MatchupComparison:
    base = {
        (item.opponent_rank, item.opponent_name, item.shields): item
        for item in records if item.candidate_id == baseline
    }
    changed = {
        (item.opponent_rank, item.opponent_name, item.shields): item
        for item in records if item.candidate_id == variant
    }
    if base.keys() != changed.keys():
        raise ValueError(f"incomplete comparison matrix for {name}")
    gained: list[str] = []
    lost: list[str] = []
    for key in sorted(base):
        base_win = base[key].result.candidate_rating > 500
        changed_win = changed[key].result.candidate_rating > 500
        label = (
            f"#{key[0]} {key[1]} ({key[2]} shields: "
            f"{base[key].result.candidate_rating}→"
            f"{changed[key].result.candidate_rating})"
        )
        if changed_win and not base_win:
            gained.append(label)
        elif base_win and not changed_win:
            lost.append(label)
    base_ratings = [item.result.candidate_rating for item in base.values()]
    changed_ratings = [item.result.candidate_rating for item in changed.values()]
    return MatchupComparison(
        name,
        baseline,
        variant,
        fmean(changed_ratings) - fmean(base_ratings),
        (
            sum(value > 500 for value in changed_ratings)
            - sum(value > 500 for value in base_ratings)
        ) / len(base_ratings),
        tuple(gained),
        tuple(lost),
    )


MATCHUP_FIELDS: Final = (
    "candidate_id", "opponent_rank", "opponent_name", "opponent_id", "shields",
    "outcome", "battle_rating", "opponent_rating", "remaining_hp",
    "opponent_remaining_hp", "candidate_cp", "candidate_level", "candidate_ivs",
    "opponent_cp", "opponent_level", "opponent_ivs",
)


def write_matchups(path: Path | str, records: Sequence[MatchupRecord]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MATCHUP_FIELDS)
        writer.writeheader()
        for item in records:
            result = item.result
            writer.writerow({
                "candidate_id": item.candidate_id,
                "opponent_rank": item.opponent_rank,
                "opponent_name": item.opponent_name,
                "opponent_id": item.opponent_id,
                "shields": item.shields,
                "outcome": result.outcome,
                "battle_rating": result.candidate_rating,
                "opponent_rating": result.opponent_rating,
                "remaining_hp": result.candidate_remaining_hp,
                "opponent_remaining_hp": result.opponent_remaining_hp,
                "candidate_cp": result.candidate_build.cp,
                "candidate_level": result.candidate_build.level,
                "candidate_ivs": (
                    f"{result.candidate_build.attack_iv}/"
                    f"{result.candidate_build.defense_iv}/"
                    f"{result.candidate_build.hp_iv}"
                ),
                "opponent_cp": result.opponent_build.cp,
                "opponent_level": result.opponent_build.level,
                "opponent_ivs": (
                    f"{result.opponent_build.attack_iv}/"
                    f"{result.opponent_build.defense_iv}/"
                    f"{result.opponent_build.hp_iv}"
                ),
            })


def write_summary(
    path: Path | str,
    *,
    meta_size: int,
    movesets: Sequence[MovesetSummary],
    teams: Sequence[TeamSummary],
    comparisons: Sequence[MatchupComparison],
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "method": {
            "engine": "vendored official PvPoke battle engine",
            "pvpoke_commit": VENDORED_PVPOKE_COMMIT,
            "shield_scenarios": list(SHIELD_SCENARIOS),
            "starting_energy": 0,
            "starting_hp": "full",
            "default_build": "GameMaster defaultIVs cp1500, level cap 50",
            "meta_size": meta_size,
            "robustness_formula": (
                "100 * (0.60 * coverage_rate + 0.20 * depth_rate + "
                "0.20 * average_battle_rating / 1000)"
            ),
        },
        "movesets": [asdict(item) for item in movesets],
        "teams": [asdict(item) for item in teams],
        "comparisons": [asdict(item) for item in comparisons],
    }
    with output.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
