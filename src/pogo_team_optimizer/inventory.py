"""Owned-instance ingestion and ranking intersection for inventory mode."""

import csv
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from collections.abc import Sequence

from pogo_team_optimizer.models import InventoryPokemon, MoveKind, PokemonCandidate
from pogo_team_optimizer.parsing.gamemaster import GameMaster, MoveResolutionError


class InventoryError(ValueError):
    pass


class InventoryStatus(StrEnum):
    BATTLE_READY = "battle-ready"
    DIFFERENT_MOVES = "different-moves"
    MISSING_MOVE = "missing-move"
    WRONG_FORM = "wrong-form"
    SPECIES_NOT_RANKED = "species-not-ranked"


@dataclass(frozen=True, slots=True)
class InventoryDiagnostic:
    instance_id: str
    status: InventoryStatus
    message: str


def _boolean(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes", "y", "是"}:
        return True
    if normalized in {"false", "0", "no", "n", "否", ""}:
        return False
    raise InventoryError(f"無法解析 shadow 值：{value!r}")


def read_inventory(path: Path | str) -> list[InventoryPokemon]:
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"instance_id", "pokemon_name", "shadow", "cp", "fast_move", "charged_move_1"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise InventoryError(f"庫存 CSV 缺少必要欄位：{', '.join(sorted(missing))}")
        result: list[InventoryPokemon] = []
        seen: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            instance_id = row["instance_id"].strip()
            if not instance_id or instance_id in seen:
                raise InventoryError(f"第 {row_number} 列 instance_id 空白或重複")
            seen.add(instance_id)
            try:
                cp = int(row["cp"])
            except ValueError as error:
                raise InventoryError(f"第 {row_number} 列 CP 無效：{row['cp']!r}") from error
            optional = lambda key: (row.get(key) or "").strip() or None
            result.append(
                InventoryPokemon(
                    instance_id, row["pokemon_name"].strip(), optional("form"),
                    _boolean(row["shadow"]), cp, optional("fast_move"),
                    optional("charged_move_1"), optional("charged_move_2"),
                    optional("notes") or "",
                )
            )
    return result


def inventory_candidates(
    inventory: Sequence[InventoryPokemon],
    rankings: Sequence[PokemonCandidate],
    game_master: GameMaster,
    cp_cap: int | None = None,
) -> tuple[list[PokemonCandidate], list[InventoryDiagnostic]]:
    """Intersect all rankings with owned instances, then apply actual moves."""
    ranked_by_id = {candidate.species_id: candidate for candidate in rankings}
    output: list[PokemonCandidate] = []
    diagnostics: list[InventoryDiagnostic] = []
    for owned in inventory:
        if cp_cap is not None and owned.cp > cp_cap:
            diagnostics.append(InventoryDiagnostic(owned.instance_id, InventoryStatus.WRONG_FORM, f"CP {owned.cp} 超過上限 {cp_cap}"))
            continue
        label = owned.pokemon_name
        if owned.form:
            label = f"{label}_{owned.form}"
        try:
            base_id = game_master.resolve_species_id(label)
        except MoveResolutionError:
            try:
                base_id = game_master.resolve_species_id(owned.pokemon_name)
            except MoveResolutionError as error:
                diagnostics.append(InventoryDiagnostic(owned.instance_id, InventoryStatus.SPECIES_NOT_RANKED, str(error)))
                continue
        species_id = base_id
        if owned.shadow and not species_id.endswith("_shadow"):
            species_id += "_shadow"
        if not owned.shadow and species_id.endswith("_shadow"):
            species_id = species_id.removesuffix("_shadow")
        theoretical = ranked_by_id.get(species_id)
        if theoretical is None:
            alternate = species_id.removesuffix("_shadow") if owned.shadow else f"{species_id}_shadow"
            status = InventoryStatus.WRONG_FORM if alternate in ranked_by_id else InventoryStatus.SPECIES_NOT_RANKED
            diagnostics.append(InventoryDiagnostic(owned.instance_id, status, f"排名中找不到正確形態：{species_id}"))
            continue
        if not owned.fast_move or not owned.charged_move_1:
            diagnostics.append(InventoryDiagnostic(owned.instance_id, InventoryStatus.MISSING_MOVE, "缺少快速招式或第一個蓄力招式"))
            continue
        try:
            fast = game_master.resolve_move(owned.fast_move, MoveKind.FAST)
            charged = tuple(
                game_master.resolve_move(move, MoveKind.CHARGED)
                for move in (owned.charged_move_1, owned.charged_move_2)
                if move
            )
        except MoveResolutionError as error:
            diagnostics.append(InventoryDiagnostic(owned.instance_id, InventoryStatus.MISSING_MOVE, str(error)))
            continue
        metadata = game_master.pokemon_by_id[species_id]
        if fast.move_id not in metadata.fast_move_ids or any(
            move.move_id not in metadata.charged_move_ids for move in charged
        ):
            diagnostics.append(InventoryDiagnostic(owned.instance_id, InventoryStatus.MISSING_MOVE, "招式不在該形態的 GameMaster 招式池"))
            continue
        actual = PokemonCandidate(theoretical.ranking, species_id, fast, charged, owned.instance_id)
        recommended_ids = tuple(move.move_id for move in theoretical.moves)
        actual_ids = tuple(move.move_id for move in actual.moves)
        status = InventoryStatus.BATTLE_READY if actual_ids == recommended_ids else InventoryStatus.DIFFERENT_MOVES
        diagnostics.append(InventoryDiagnostic(owned.instance_id, status, "實際招式等同建議" if status is InventoryStatus.BATTLE_READY else "以實際招式評分（不同於 PvPoke 建議）"))
        output.append(actual)
    output.sort(key=lambda value: (value.rank, value.instance_id or ""))
    return output, diagnostics
