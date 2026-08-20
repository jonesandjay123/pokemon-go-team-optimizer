"""Owned-instance ingestion and ranking intersection for inventory mode."""

import csv
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from collections.abc import Sequence

from pogo_team_optimizer.models import InventoryPokemon, MoveKind, PokemonCandidate
from pogo_team_optimizer.parsing.gamemaster import GameMaster, MoveResolutionError
from pogo_team_optimizer.scoring.move_quality import score_moveset_quality
from pogo_team_optimizer.readiness import (
    DEFAULT_READINESS_CONFIG,
    ReadinessAssessment,
    ReadinessConfig,
    ReadinessStatus,
    assess_readiness,
)


class InventoryError(ValueError):
    pass


class InventoryStatus(StrEnum):
    BATTLE_READY = "battle-ready"
    DIFFERENT_MOVES = "different-moves"
    MISSING_MOVE = "missing-move"
    WRONG_FORM = "wrong-form"
    INELIGIBLE_CP = "ineligible-cp"
    SPECIES_NOT_RANKED = "species-not-ranked"


@dataclass(frozen=True, slots=True)
class InventoryDiagnostic:
    instance_id: str
    status: InventoryStatus
    message: str
    species_id: str | None = None
    team_species_key: str | None = None
    actual_moves: tuple[str, ...] = ()
    recommended_moves: tuple[str, ...] = ()
    moveset_match: str | None = None
    actual_move_quality: float | None = None
    recommended_move_quality: float | None = None
    move_quality_delta: float | None = None
    second_charged_move_missing: bool = False
    readiness: ReadinessAssessment | None = None


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
            pokemon_name = row["pokemon_name"].strip()
            if not pokemon_name:
                raise InventoryError(f"第 {row_number} 列 pokemon_name 不可空白")
            try:
                cp = int(row["cp"])
            except ValueError as error:
                raise InventoryError(f"第 {row_number} 列 CP 無效：{row['cp']!r}") from error
            if cp <= 0:
                raise InventoryError(f"第 {row_number} 列 CP 必須大於 0")

            def optional(key: str) -> str | None:
                return (row.get(key) or "").strip() or None

            result.append(
                InventoryPokemon(
                    instance_id, pokemon_name, optional("form"),
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
    readiness_config: ReadinessConfig = DEFAULT_READINESS_CONFIG,
) -> tuple[list[PokemonCandidate], list[InventoryDiagnostic]]:
    """Intersect all rankings with owned instances, then apply actual moves."""
    ranked_by_id = {candidate.species_id: candidate for candidate in rankings}
    output: list[PokemonCandidate] = []
    diagnostics: list[InventoryDiagnostic] = []
    readiness_cap = cp_cap or 10_000
    for owned in inventory:
        raw_actual_moves = owned.move_names
        label = owned.pokemon_name
        if owned.form:
            label = f"{label}_{owned.form}"
        try:
            base_id = game_master.resolve_species_id(label)
        except MoveResolutionError as form_error:
            if owned.form:
                diagnostics.append(
                    InventoryDiagnostic(
                        owned.instance_id,
                        InventoryStatus.WRONG_FORM,
                        f"無法解析指定形態 {owned.form!r}：{form_error}",
                        actual_moves=raw_actual_moves,
                        readiness=assess_readiness(
                            owned.cp,
                            0,
                            readiness_cap,
                            readiness_config,
                            ReadinessStatus.MISSING_SPECIES_FORM,
                        ),
                    )
                )
                continue
            try:
                base_id = game_master.resolve_species_id(owned.pokemon_name)
            except MoveResolutionError as error:
                diagnostics.append(
                    InventoryDiagnostic(
                        owned.instance_id,
                        InventoryStatus.SPECIES_NOT_RANKED,
                        str(error),
                        actual_moves=raw_actual_moves,
                        readiness=assess_readiness(
                            owned.cp,
                            0,
                            readiness_cap,
                            readiness_config,
                            ReadinessStatus.MISSING_SPECIES_FORM,
                        ),
                    )
                )
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
            metadata = game_master.pokemon_by_id.get(species_id)
            diagnostics.append(
                InventoryDiagnostic(
                    owned.instance_id,
                    status,
                    f"排名中找不到正確形態：{species_id}",
                    species_id=species_id,
                    team_species_key=(f"dex:{metadata.dex}" if metadata else None),
                    actual_moves=raw_actual_moves,
                    readiness=assess_readiness(
                        owned.cp,
                        0,
                        readiness_cap,
                        readiness_config,
                        ReadinessStatus.MISSING_SPECIES_FORM,
                    ),
                )
            )
            continue
        if cp_cap is not None and owned.cp > cp_cap:
            diagnostics.append(
                InventoryDiagnostic(
                    owned.instance_id,
                    InventoryStatus.INELIGIBLE_CP,
                    f"CP {owned.cp} 超過上限 {cp_cap}",
                    species_id=species_id,
                    team_species_key=theoretical.team_species_key,
                    actual_moves=raw_actual_moves,
                    recommended_moves=tuple(
                        move.name for move in theoretical.recommended_moves
                    ),
                    readiness=assess_readiness(
                        owned.cp,
                        theoretical.ranking.cp,
                        readiness_cap,
                        readiness_config,
                        ReadinessStatus.INELIGIBLE_OVER_CAP,
                    ),
                )
            )
            continue
        if not owned.fast_move or not owned.charged_move_1:
            diagnostics.append(
                InventoryDiagnostic(
                    owned.instance_id,
                    InventoryStatus.MISSING_MOVE,
                    "缺少快速招式或第一個蓄力招式",
                    species_id=species_id,
                    team_species_key=theoretical.team_species_key,
                    actual_moves=raw_actual_moves,
                    recommended_moves=tuple(
                        move.name for move in theoretical.recommended_moves
                    ),
                    second_charged_move_missing=not owned.charged_move_2,
                    readiness=assess_readiness(
                        owned.cp,
                        theoretical.ranking.cp,
                        readiness_cap,
                        readiness_config,
                        ReadinessStatus.INVALID_MISSING_MOVE,
                    ),
                )
            )
            continue
        try:
            fast = game_master.resolve_move(owned.fast_move, MoveKind.FAST)
            charged = tuple(
                game_master.resolve_move(move, MoveKind.CHARGED)
                for move in (owned.charged_move_1, owned.charged_move_2)
                if move
            )
        except MoveResolutionError as error:
            diagnostics.append(
                InventoryDiagnostic(
                    owned.instance_id,
                    InventoryStatus.MISSING_MOVE,
                    str(error),
                    species_id=species_id,
                    team_species_key=theoretical.team_species_key,
                    actual_moves=raw_actual_moves,
                    recommended_moves=tuple(
                        move.name for move in theoretical.recommended_moves
                    ),
                    readiness=assess_readiness(
                        owned.cp,
                        theoretical.ranking.cp,
                        readiness_cap,
                        readiness_config,
                        ReadinessStatus.INVALID_MISSING_MOVE,
                    ),
                )
            )
            continue
        metadata = game_master.pokemon_by_id[species_id]
        if fast.move_id not in metadata.fast_move_ids or any(
            move.move_id not in metadata.charged_move_ids for move in charged
        ):
            diagnostics.append(
                InventoryDiagnostic(
                    owned.instance_id,
                    InventoryStatus.MISSING_MOVE,
                    "招式不在該形態的 GameMaster 招式池",
                    species_id=species_id,
                    team_species_key=theoretical.team_species_key,
                    actual_moves=raw_actual_moves,
                    recommended_moves=tuple(
                        move.name for move in theoretical.recommended_moves
                    ),
                    readiness=assess_readiness(
                        owned.cp,
                        theoretical.ranking.cp,
                        readiness_cap,
                        readiness_config,
                        ReadinessStatus.INVALID_MISSING_MOVE,
                    ),
                )
            )
            continue
        actual = PokemonCandidate(
            theoretical.ranking,
            species_id,
            theoretical.team_species_key,
            fast,
            charged,
            owned.instance_id,
            theoretical.fast_move,
            theoretical.charged_moves,
        )
        recommended_ids = tuple(move.move_id for move in theoretical.recommended_moves)
        actual_ids = tuple(move.move_id for move in actual.moves)
        exact = (
            actual.fast_move.move_id == theoretical.fast_move.move_id
            and {move.move_id for move in actual.charged_moves}
            == {move.move_id for move in theoretical.charged_moves}
        )
        actual_set = set(actual_ids)
        recommended_set = set(recommended_ids)
        match = "exact" if exact else "partial" if actual_set & recommended_set else "different"
        status = InventoryStatus.BATTLE_READY if exact else InventoryStatus.DIFFERENT_MOVES
        actual_quality = score_moveset_quality(actual.fast_move, actual.charged_moves)
        recommended_quality = score_moveset_quality(
            theoretical.fast_move, theoretical.charged_moves
        )
        diagnostics.append(
            InventoryDiagnostic(
                owned.instance_id,
                status,
                "實際招式等同建議" if exact else "以實際合法招式評分",
                species_id,
                theoretical.team_species_key,
                tuple(move.name for move in actual.moves),
                tuple(move.name for move in theoretical.moves),
                match,
                actual_quality.total_score,
                recommended_quality.total_score,
                actual_quality.total_score - recommended_quality.total_score,
                len(actual.charged_moves) == 1,
                assess_readiness(
                    owned.cp,
                    theoretical.ranking.cp,
                    readiness_cap,
                    readiness_config,
                ),
            )
        )
        output.append(actual)
    output.sort(key=lambda value: (value.rank, value.instance_id or ""))
    return output, diagnostics


def team_buildability_reasons(
    team: Sequence[PokemonCandidate],
    eligible: Sequence[PokemonCandidate],
    diagnostics: Sequence[InventoryDiagnostic],
) -> tuple[str, ...]:
    """Explain buildability without requiring recommended moves."""
    reasons: list[str] = []
    for member in team:
        matching_eligible = [
            candidate for candidate in eligible if candidate.species_id == member.species_id
        ]
        matching_diagnostics = [
            item for item in diagnostics if item.species_id == member.species_id
        ]
        same_species_other_form = [
            item
            for item in diagnostics
            if item.team_species_key == member.team_species_key
            and item.species_id != member.species_id
        ]
        if matching_eligible:
            details: list[str] = ["eligible instance owned"]
            readiness_statuses = {
                item.readiness.status
                for item in matching_diagnostics
                if item.readiness is not None
            }
            if ReadinessStatus.READY_NOW in readiness_statuses:
                details.append("ready now")
            elif ReadinessStatus.POWER_UP_NEEDED in readiness_statuses:
                details.append("power-up needed")
            if any(item.moveset_match != "exact" for item in matching_diagnostics):
                details.append("actual moves differ")
            if any(item.second_charged_move_missing for item in matching_diagnostics):
                details.append("second charged move missing")
            reason = ", ".join(details)
        elif matching_diagnostics:
            reason = "correct form owned, but no eligible valid moveset"
        elif same_species_other_form:
            reason = "species owned, but wrong Shadow/normal form"
        else:
            reason = "species not owned"
        reasons.append(f"{member.name}: {reason}")
    return tuple(reasons)


def readiness_by_instance(
    diagnostics: Sequence[InventoryDiagnostic],
) -> dict[str, ReadinessAssessment]:
    return {
        item.instance_id: item.readiness
        for item in diagnostics
        if item.readiness is not None
    }


def ready_now_candidates(
    candidates: Sequence[PokemonCandidate],
    diagnostics: Sequence[InventoryDiagnostic],
) -> list[PokemonCandidate]:
    assessments = readiness_by_instance(diagnostics)
    return [
        candidate
        for candidate in candidates
        if candidate.instance_id is not None
        and assessments[candidate.instance_id].status is ReadinessStatus.READY_NOW
    ]


def team_power_up_gaps(
    team: Sequence[PokemonCandidate],
    diagnostics: Sequence[InventoryDiagnostic],
) -> tuple[tuple[str, int, int, int], ...]:
    assessments = readiness_by_instance(diagnostics)
    return tuple(
        (
            candidate.name,
            assessment.actual_cp,
            assessment.target_cp,
            assessment.cp_gap,
        )
        for candidate in team
        if candidate.instance_id is not None
        and (assessment := assessments[candidate.instance_id]).status
        is ReadinessStatus.POWER_UP_NEEDED
    )
