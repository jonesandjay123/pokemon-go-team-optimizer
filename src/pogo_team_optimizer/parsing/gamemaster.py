"""PvPoke GameMaster ingestion and explicit name resolution."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from pogo_team_optimizer.models import Move, MoveKind, PokemonCandidate, RankingEntry
from pogo_team_optimizer.type_chart import PokemonType, parse_type


class MoveResolutionError(ValueError):
    pass


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    return "".join(character for character in value if character.isalnum())


@dataclass(frozen=True, slots=True)
class PokemonMetadata:
    dex: int
    species_id: str
    name: str
    fast_move_ids: tuple[str, ...]
    charged_move_ids: tuple[str, ...]
    types: tuple[PokemonType, ...]


@dataclass(frozen=True, slots=True)
class GameMaster:
    moves_by_id: Mapping[str, Move]
    pokemon_by_id: Mapping[str, PokemonMetadata]
    move_aliases: Mapping[str, str]
    pokemon_aliases: Mapping[str, str]

    def resolve_move(self, value: str, expected_kind: MoveKind | None = None) -> Move:
        key = normalize_name(value)
        move_id = self.move_aliases.get(key, value.strip().upper().replace(" ", "_"))
        try:
            move = self.moves_by_id[move_id]
        except KeyError as error:
            raise MoveResolutionError(f"無法解析招式：{value!r}") from error
        if expected_kind is not None and move.kind is not expected_kind:
            raise MoveResolutionError(
                f"招式 {value!r} 是 {move.kind.value}，預期 {expected_kind.value}"
            )
        return move

    def resolve_species_id(self, value: str) -> str:
        key = normalize_name(value)
        species_id = self.pokemon_aliases.get(
            key, value.strip().casefold().replace(" ", "_")
        )
        if species_id not in self.pokemon_by_id:
            raise MoveResolutionError(f"無法解析寶可夢／形態：{value!r}")
        return species_id


def _move_kind(raw: Mapping[str, Any]) -> MoveKind:
    return MoveKind.FAST if float(raw.get("energyGain", 0) or 0) > 0 else MoveKind.CHARGED


def _aliases(path: Path | str | None) -> tuple[dict[str, str], dict[str, str]]:
    if path is None:
        return {}, {}
    with Path(path).open(encoding="utf-8") as file:
        raw = json.load(file)
    return (
        {normalize_name(k): v for k, v in raw.get("moves", {}).items()},
        {normalize_name(k): v for k, v in raw.get("pokemon", {}).items()},
    )


def read_game_master(path: Path | str, aliases_path: Path | str | None = None) -> GameMaster:
    with Path(path).open(encoding="utf-8") as file:
        raw = json.load(file)
    move_aliases, pokemon_aliases = _aliases(aliases_path)
    moves: dict[str, Move] = {}
    for item in raw.get("moves", []):
        move_id = item["moveId"]
        move = Move(
            move_id=move_id,
            name=item.get("name", move_id),
            move_type=parse_type(item["type"]),
            kind=_move_kind(item),
            power=float(item.get("power", 0) or 0),
            energy=float(item.get("energy", 0) or 0),
            energy_gain=float(item.get("energyGain", 0) or 0),
            cooldown=float(item.get("cooldown", 0) or 0),
            turns=int(
                item.get("turns")
                or max(1, round(float(item.get("cooldown", 500) or 500) / 500))
            ),
            buffs=tuple(int(value) for value in item.get("buffs", [])),
            buff_target=item.get("buffTarget"),
            buff_apply_chance=(
                float(item["buffApplyChance"])
                if item.get("buffApplyChance") is not None
                else None
            ),
        )
        moves[move_id] = move
        for label in (move_id, move.name, item.get("abbreviation")):
            if label:
                move_aliases.setdefault(normalize_name(label), move_id)

    pokemon: dict[str, PokemonMetadata] = {}
    for item in raw.get("pokemon", []):
        species_id = item["speciesId"]
        pokemon[species_id] = PokemonMetadata(
            dex=int(item["dex"]),
            species_id=species_id,
            name=item.get("speciesName", species_id),
            fast_move_ids=tuple(item.get("fastMoves", [])),
            charged_move_ids=tuple(item.get("chargedMoves", [])),
            types=tuple(
                parse_type(value)
                for value in item.get("types", [])
                if value and str(value).casefold() not in {"none", "null"}
            ),
        )
        for label in (species_id, item.get("speciesName")):
            if label:
                pokemon_aliases.setdefault(normalize_name(label), species_id)
    return GameMaster(moves, pokemon, move_aliases, pokemon_aliases)


def infer_shadow(value: str) -> bool:
    normalized = normalize_name(value)
    return "shadow" in normalized or "暗影" in value


def resolve_ranking_entries(
    entries: Sequence[RankingEntry],
    game_master: GameMaster,
    species_ids: Sequence[str] | None = None,
) -> tuple[list[PokemonCandidate], list[str]]:
    candidates: list[PokemonCandidate] = []
    unresolved: list[str] = []
    for index, entry in enumerate(entries):
        try:
            species_id = (
                species_ids[index]
                if species_ids is not None
                else game_master.resolve_species_id(entry.name)
            )
            fast = game_master.resolve_move(entry.fast_move, MoveKind.FAST)
            charged = tuple(
                game_master.resolve_move(move, MoveKind.CHARGED)
                for move in entry.charged_moves
            )
            if not charged:
                raise MoveResolutionError("沒有可用的蓄力招式")
            metadata = game_master.pokemon_by_id[species_id]
            if fast.move_id not in metadata.fast_move_ids:
                raise MoveResolutionError(f"{fast.name} 不在 {metadata.name} 的快速招式池")
            illegal = [move.name for move in charged if move.move_id not in metadata.charged_move_ids]
            if illegal:
                raise MoveResolutionError(f"{', '.join(illegal)} 不在 {metadata.name} 的蓄力招式池")
            team_species_key = f"dex:{metadata.dex}"
            candidates.append(
                PokemonCandidate(
                    entry,
                    species_id,
                    team_species_key,
                    fast,
                    charged,
                    recommended_fast_move=fast,
                    recommended_charged_moves=charged,
                )
            )
        except (MoveResolutionError, IndexError) as error:
            unresolved.append(f"#{entry.rank} {entry.name}: {error}")
    return candidates, unresolved
