from pogo_team_optimizer.models import RankingEntry
from pogo_team_optimizer.type_chart import PokemonType


def ranking_entry(
    rank: int,
    name: str,
    primary_type: PokemonType,
    secondary_type: PokemonType | None = None,
    score: float = 90.0,
) -> RankingEntry:
    return RankingEntry(
        rank=rank,
        name=name,
        score=score,
        primary_type=primary_type,
        secondary_type=secondary_type,
        attack=110.0,
        defense=120.0,
        hp=140,
        level=25.0,
        cp=1500,
        fast_move="Fast Move",
        charged_moves=("Charged Move 1", "Charged Move 2"),
    )
