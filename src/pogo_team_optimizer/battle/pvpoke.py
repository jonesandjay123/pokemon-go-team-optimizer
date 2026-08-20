"""Batch bridge to the vendored official PvPoke JavaScript battle engine."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence


VENDORED_PVPOKE_COMMIT: Final = "ea601f0a61c548f9140e4605b94a31fa97fe6aba"


class PvPokeBridgeError(RuntimeError):
    """Raised when the external Node runtime or PvPoke engine fails."""


@dataclass(frozen=True, slots=True)
class Moveset:
    species_id: str
    fast_move: str
    charged_moves: tuple[str, ...]
    label: str = ""

    def __post_init__(self) -> None:
        if not self.species_id or not self.fast_move:
            raise ValueError("species_id and fast_move are required")
        if not 1 <= len(self.charged_moves) <= 2:
            raise ValueError("a battle moveset requires one or two charged moves")
        if len(set(self.charged_moves)) != len(self.charged_moves):
            raise ValueError("charged moves must be distinct")

    def to_bridge_json(self) -> dict[str, object]:
        return {
            "species_id": self.species_id,
            "fast_move": self.fast_move,
            "charged_moves": list(self.charged_moves),
        }


@dataclass(frozen=True, slots=True)
class BattleMatchup:
    request_id: str
    candidate: Moveset
    opponent: Moveset
    shields: int

    def __post_init__(self) -> None:
        if self.shields not in {0, 1, 2}:
            raise ValueError("shields must be 0, 1, or 2")


@dataclass(frozen=True, slots=True)
class BattleBuild:
    species_id: str
    cp: int
    level: float
    attack_iv: int
    defense_iv: int
    hp_iv: int
    max_hp: int
    attack: float
    defense: float


@dataclass(frozen=True, slots=True)
class BattleResult:
    request_id: str
    shields: int
    candidate_rating: int
    opponent_rating: int
    outcome: str
    candidate_remaining_hp: int
    opponent_remaining_hp: int
    candidate_build: BattleBuild
    opponent_build: BattleBuild


def _build(value: dict[str, object]) -> BattleBuild:
    ivs = value["ivs"]
    if not isinstance(ivs, dict):
        raise PvPokeBridgeError("PvPoke returned malformed IV data")
    return BattleBuild(
        species_id=str(value["species_id"]),
        cp=int(value["cp"]),
        level=float(value["level"]),
        attack_iv=int(ivs["atk"]),
        defense_iv=int(ivs["def"]),
        hp_iv=int(ivs["hp"]),
        max_hp=int(value["max_hp"]),
        attack=float(value["attack"]),
        defense=float(value["defense"]),
    )


class PvPokeEngine:
    """Run deterministic equal-state 1v1 simulations through PvPoke."""

    def __init__(
        self,
        gamemaster_path: Path | str,
        node_binary: str | None = None,
        runner_path: Path | str | None = None,
        cp_cap: int = 1500,
        level_cap: int = 50,
    ) -> None:
        self.gamemaster_path = Path(gamemaster_path).resolve()
        if not self.gamemaster_path.is_file():
            raise PvPokeBridgeError(f"GameMaster not found: {self.gamemaster_path}")
        node = node_binary or shutil.which("node")
        if not node:
            raise PvPokeBridgeError(
                "V3 requires Node.js to run the vendored PvPoke battle engine"
            )
        self.node_binary = node
        self.runner_path = Path(
            runner_path
            or Path(__file__).parent / "vendor" / "pvpoke" / "runner.js"
        ).resolve()
        if not self.runner_path.is_file():
            raise PvPokeBridgeError(f"PvPoke runner not found: {self.runner_path}")
        if cp_cap <= 0 or level_cap <= 0:
            raise ValueError("cp_cap and level_cap must be positive")
        self.cp_cap = cp_cap
        self.level_cap = level_cap

    def simulate(self, matchups: Sequence[BattleMatchup]) -> list[BattleResult]:
        if not matchups:
            return []
        request = {
            "gamemaster_path": str(self.gamemaster_path),
            "cp_cap": self.cp_cap,
            "level_cap": self.level_cap,
            "matchups": [
                {
                    "request_id": matchup.request_id,
                    "candidate": matchup.candidate.to_bridge_json(),
                    "opponent": matchup.opponent.to_bridge_json(),
                    "shields": matchup.shields,
                }
                for matchup in matchups
            ],
        }
        completed = subprocess.run(
            [self.node_binary, str(self.runner_path)],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise PvPokeBridgeError(f"PvPoke simulation failed: {detail}")
        try:
            raw = json.loads(completed.stdout)
            rows = raw["results"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise PvPokeBridgeError("PvPoke returned malformed JSON") from error
        if len(rows) != len(matchups):
            raise PvPokeBridgeError(
                f"PvPoke returned {len(rows)} results for {len(matchups)} matchups"
            )
        return [
            BattleResult(
                request_id=str(row["request_id"]),
                shields=int(row["shields"]),
                candidate_rating=int(row["candidate_rating"]),
                opponent_rating=int(row["opponent_rating"]),
                outcome=str(row["outcome"]),
                candidate_remaining_hp=int(row["candidate_remaining_hp"]),
                opponent_remaining_hp=int(row["opponent_remaining_hp"]),
                candidate_build=_build(row["candidate_build"]),
                opponent_build=_build(row["opponent_build"]),
            )
            for row in rows
        ]
