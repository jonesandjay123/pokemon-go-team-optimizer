"""Ingest PvPoke's machine-readable ranking JSON."""

import json
from pathlib import Path

from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.parsing.gamemaster import GameMaster


def read_rankings_json(
    path: Path | str, game_master: GameMaster
) -> tuple[list[RankingEntry], list[str]]:
    with Path(path).open(encoding="utf-8") as file:
        raw = json.load(file)
    entries: list[RankingEntry] = []
    species_ids: list[str] = []
    for rank, item in enumerate(raw, start=1):
        species_id = item["speciesId"]
        metadata = game_master.pokemon_by_id[species_id]
        types = metadata.types
        moveset = item["moveset"]
        stats = item.get("stats", {})
        entries.append(
            RankingEntry(
                rank=rank,
                name=item.get("speciesName", metadata.name),
                score=float(item["score"]),
                primary_type=types[0],
                secondary_type=types[1] if len(types) > 1 else None,
                attack=float(stats.get("atk", 0)),
                defense=float(stats.get("def", 0)),
                hp=int(stats.get("hp", 0)),
                level=0,
                cp=0,
                fast_move=moveset[0],
                charged_moves=tuple(moveset[1:]),
            )
        )
        species_ids.append(species_id)
    return entries, species_ids
