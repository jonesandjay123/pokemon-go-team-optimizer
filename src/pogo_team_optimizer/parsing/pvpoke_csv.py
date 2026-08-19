"""Parser for official PvPoke and PvPokeTW ranking CSV exports."""

import csv
import unicodedata
from collections.abc import Sequence
from pathlib import Path

from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.type_chart import parse_type


class RankingParseError(ValueError):
    """Raised when ranking input cannot be normalized safely."""


def _header_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lstrip("\ufeff").lower()
    return "".join(character for character in normalized if character.isalnum())


HEADER_ALIASES: dict[str, frozenset[str]] = {
    "name": frozenset({"pokemon", "pokémon", "name", "名稱", "寶可夢"}),
    "score": frozenset({"score", "評分"}),
    "primary_type": frozenset({"type1", "primarytype", "第一屬性"}),
    "secondary_type": frozenset({"type2", "secondarytype", "第二屬性"}),
    "attack": frozenset({"attack", "atk", "攻擊", "攻擊力"}),
    "defense": frozenset({"defense", "def", "防禦", "防禦力"}),
    "hp": frozenset({"stamina", "hp", "耐力"}),
    "level": frozenset({"level", "等級"}),
    "cp": frozenset({"cp"}),
    "fast_move": frozenset({"fastmove", "一般招式", "快速招式"}),
    "charged_move_1": frozenset({"chargedmove1", "特殊招式1", "蓄力招式1"}),
    "charged_move_2": frozenset({"chargedmove2", "特殊招式2", "蓄力招式2"}),
}

REQUIRED_FIELDS = (
    "name",
    "score",
    "primary_type",
    "secondary_type",
    "attack",
    "defense",
    "hp",
    "level",
    "cp",
    "fast_move",
    "charged_move_1",
    "charged_move_2",
)


def _canonical_field(header: str) -> str | None:
    key = _header_key(header)
    for field, aliases in HEADER_ALIASES.items():
        if key in aliases:
            return field
    return None


def repair_malformed_header(
    header: Sequence[str], rows: Sequence[Sequence[str]]
) -> tuple[list[str], bool]:
    """Insert the CP header only for the known PvPokeTW export defect."""
    repaired = list(header)
    nonempty_rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not nonempty_rows:
        return repaired, False

    widths = {len(row) for row in nonempty_rows}
    if widths == {len(repaired)}:
        return repaired, False

    canonical = [_canonical_field(column) for column in repaired]
    try:
        level_index = canonical.index("level")
        fast_move_index = canonical.index("fast_move")
    except ValueError as error:
        raise RankingParseError(
            "CSV 欄數不一致，且無法辨識 PvPokeTW 的 Level/CP header 問題"
        ) from error

    known_tw_defect = (
        widths == {len(repaired) + 1}
        and "cp" not in canonical
        and fast_move_index == level_index + 1
    )
    if not known_tw_defect:
        raise RankingParseError(
            f"CSV header 有 {len(repaired)} 欄，但資料列欄數為 {sorted(widths)}"
        )

    repaired.insert(level_index + 1, "CP")
    return repaired, True


def _field_indexes(header: Sequence[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for index, column in enumerate(header):
        canonical = _canonical_field(column)
        if canonical is not None and canonical not in indexes:
            indexes[canonical] = index

    missing = [field for field in REQUIRED_FIELDS if field not in indexes]
    if missing:
        raise RankingParseError(f"CSV 缺少必要欄位：{', '.join(missing)}")
    return indexes


def _number(value: str, field: str, row_number: int) -> float:
    try:
        return float(value.strip())
    except ValueError as error:
        raise RankingParseError(
            f"第 {row_number} 列的 {field} 不是有效數字：{value!r}"
        ) from error


def read_rankings(path: Path | str) -> list[RankingEntry]:
    """Read a ranking CSV into canonical entries, preserving source rank order."""
    csv_path = Path(path)
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            all_rows = list(csv.reader(file))
    except FileNotFoundError:
        raise

    if not all_rows:
        raise RankingParseError("排名 CSV 是空檔案")

    raw_header, raw_rows = all_rows[0], all_rows[1:]
    header, _ = repair_malformed_header(raw_header, raw_rows)
    indexes = _field_indexes(header)

    entries: list[RankingEntry] = []
    for source_row_number, row in enumerate(raw_rows, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(header):
            raise RankingParseError(
                f"第 {source_row_number} 列有 {len(row)} 欄，預期 {len(header)} 欄"
            )

        def value(field: str) -> str:
            return row[indexes[field]].strip()

        secondary_label = value("secondary_type")
        secondary_type = (
            None
            if secondary_label.lower() in {"", "none", "null", "無"}
            else parse_type(secondary_label)
        )
        charged_moves = tuple(
            move
            for move in (value("charged_move_1"), value("charged_move_2"))
            if move
        )
        entries.append(
            RankingEntry(
                rank=len(entries) + 1,
                name=value("name"),
                score=_number(value("score"), "score", source_row_number),
                primary_type=parse_type(value("primary_type")),
                secondary_type=secondary_type,
                attack=_number(value("attack"), "attack", source_row_number),
                defense=_number(value("defense"), "defense", source_row_number),
                hp=int(_number(value("hp"), "hp", source_row_number)),
                level=_number(value("level"), "level", source_row_number),
                cp=int(_number(value("cp"), "cp", source_row_number)),
                fast_move=value("fast_move"),
                charged_moves=charged_moves,
            )
        )

    if not entries:
        raise RankingParseError("排名 CSV 沒有資料列")
    return entries


def select_top(entries: Sequence[RankingEntry], count: int) -> list[RankingEntry]:
    """Select the first N ranked entries with explicit size validation."""
    if count < 3:
        raise ValueError("top count must be at least 3")
    if len(entries) < count:
        raise ValueError(f"要求前 {count} 名，但輸入資料只有 {len(entries)} 筆")
    return list(entries[:count])
