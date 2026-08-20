"""Create a Traditional Chinese Great League inventory template."""

import argparse
import csv
from pathlib import Path


FIELDS = (
    "instance_id",
    "pokemon_name",
    "form",
    "shadow",
    "cp",
    "fast_move",
    "charged_move_1",
    "charged_move_2",
    "notes",
    "move_state",
)


EXAMPLE = {
    "instance_id": "gl-001",
    "pokemon_name": "寶可夢名稱（可用可靠 alias 支援的中文或英文）",
    "form": "形態；一般形態留白",
    "shadow": "false",
    "cp": "1500",
    "fast_move": "目前實際快速招式",
    "charged_move_1": "目前實際第一蓄力招式",
    "charged_move_2": "未解鎖可留白",
    "notes": "選填備註；不需要 IV",
    "move_state": "known 或 unknown；留白時由招式欄推斷",
}


def write_template(path: Path, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"檔案已存在：{path}；如要覆寫請加 --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(EXAMPLE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="建立 Great League 個體庫存 CSV 範本（繁體中文說明列）。"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/inventory/great_league.csv"),
        help="輸出位置（預設：data/inventory/great_league.csv）",
    )
    parser.add_argument("--force", action="store_true", help="允許覆寫既有檔案")
    args = parser.parse_args()
    try:
        write_template(args.output, args.force)
    except FileExistsError as error:
        parser.error(str(error))
    print(f"已建立：{args.output}")
    print("每一列必須是一隻實際個體；第二蓄力招未解鎖時留白。")
    print("請刪除或取代範例說明列，再執行 --inventory。IV 目前不需要。")
    print("尚未檢查招式可填 move_state=unknown，並使用 --scout 產生盤點優先順序。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
