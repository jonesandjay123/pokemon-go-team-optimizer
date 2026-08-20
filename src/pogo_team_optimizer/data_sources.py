"""Download upstream PvPoke data into the ignored local cache.

This module deliberately has no dependency on parsing, scoring, or search.
"""

import argparse
import os
import tempfile
import urllib.request
from pathlib import Path


RAW_ROOT = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data"
LEAGUE_CP = {"great": 1500, "ultra": 2500, "master": 10000}


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache authoritative PvPoke JSON data locally.")
    parser.add_argument("--league", choices=LEAGUE_CP, default="great")
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    cp = LEAGUE_CP[args.league]
    game_master = args.cache / "gamemaster.json"
    rankings = args.cache / f"rankings-{cp}.json"
    download(f"{RAW_ROOT}/gamemaster.json", game_master)
    download(f"{RAW_ROOT}/rankings/all/overall/rankings-{cp}.json", rankings)
    print(f"GameMaster: {game_master}")
    print(f"Rankings: {rankings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
