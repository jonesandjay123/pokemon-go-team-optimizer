"""Pokémon GO's complete 18-type defensive effectiveness chart.

The multipliers mirror PvPoke's battle calculator: super effective is 1.6,
resisted is 0.625, and a main-series immunity is represented as 0.390625.
Multipliers stack for dual-type Pokémon.
"""

from dataclasses import dataclass
from enum import StrEnum
from functools import reduce
from operator import mul
from typing import Final, Iterable


class PokemonType(StrEnum):
    NORMAL = "normal"
    FIGHTING = "fighting"
    FLYING = "flying"
    POISON = "poison"
    GROUND = "ground"
    ROCK = "rock"
    BUG = "bug"
    GHOST = "ghost"
    STEEL = "steel"
    FIRE = "fire"
    WATER = "water"
    GRASS = "grass"
    ELECTRIC = "electric"
    PSYCHIC = "psychic"
    ICE = "ice"
    DRAGON = "dragon"
    DARK = "dark"
    FAIRY = "fairy"


SUPER_EFFECTIVE: Final = 1.6
RESISTED: Final = 0.625
IMMUNE: Final = 0.390625
NEUTRAL: Final = 1.0


@dataclass(frozen=True, slots=True)
class DefensiveTraits:
    weaknesses: frozenset[PokemonType] = frozenset()
    resistances: frozenset[PokemonType] = frozenset()
    immunities: frozenset[PokemonType] = frozenset()


def _types(*values: str) -> frozenset[PokemonType]:
    return frozenset(PokemonType(value) for value in values)


TYPE_TRAITS: Final[dict[PokemonType, DefensiveTraits]] = {
    PokemonType.NORMAL: DefensiveTraits(
        weaknesses=_types("fighting"), immunities=_types("ghost")
    ),
    PokemonType.FIGHTING: DefensiveTraits(
        weaknesses=_types("flying", "psychic", "fairy"),
        resistances=_types("rock", "bug", "dark"),
    ),
    PokemonType.FLYING: DefensiveTraits(
        weaknesses=_types("rock", "electric", "ice"),
        resistances=_types("fighting", "bug", "grass"),
        immunities=_types("ground"),
    ),
    PokemonType.POISON: DefensiveTraits(
        weaknesses=_types("ground", "psychic"),
        resistances=_types("fighting", "poison", "bug", "fairy", "grass"),
    ),
    PokemonType.GROUND: DefensiveTraits(
        weaknesses=_types("water", "grass", "ice"),
        resistances=_types("poison", "rock"),
        immunities=_types("electric"),
    ),
    PokemonType.ROCK: DefensiveTraits(
        weaknesses=_types("fighting", "ground", "steel", "water", "grass"),
        resistances=_types("normal", "flying", "poison", "fire"),
    ),
    PokemonType.BUG: DefensiveTraits(
        weaknesses=_types("flying", "rock", "fire"),
        resistances=_types("fighting", "ground", "grass"),
    ),
    PokemonType.GHOST: DefensiveTraits(
        weaknesses=_types("ghost", "dark"),
        resistances=_types("poison", "bug"),
        immunities=_types("normal", "fighting"),
    ),
    PokemonType.STEEL: DefensiveTraits(
        weaknesses=_types("fighting", "ground", "fire"),
        resistances=_types(
            "normal",
            "flying",
            "rock",
            "bug",
            "steel",
            "grass",
            "psychic",
            "ice",
            "dragon",
            "fairy",
        ),
        immunities=_types("poison"),
    ),
    PokemonType.FIRE: DefensiveTraits(
        weaknesses=_types("ground", "rock", "water"),
        resistances=_types("bug", "steel", "fire", "grass", "ice", "fairy"),
    ),
    PokemonType.WATER: DefensiveTraits(
        weaknesses=_types("grass", "electric"),
        resistances=_types("steel", "fire", "water", "ice"),
    ),
    PokemonType.GRASS: DefensiveTraits(
        weaknesses=_types("flying", "poison", "bug", "fire", "ice"),
        resistances=_types("ground", "water", "grass", "electric"),
    ),
    PokemonType.ELECTRIC: DefensiveTraits(
        weaknesses=_types("ground"),
        resistances=_types("flying", "steel", "electric"),
    ),
    PokemonType.PSYCHIC: DefensiveTraits(
        weaknesses=_types("bug", "ghost", "dark"),
        resistances=_types("fighting", "psychic"),
    ),
    PokemonType.ICE: DefensiveTraits(
        weaknesses=_types("fighting", "fire", "steel", "rock"),
        resistances=_types("ice"),
    ),
    PokemonType.DRAGON: DefensiveTraits(
        weaknesses=_types("dragon", "ice", "fairy"),
        resistances=_types("fire", "water", "grass", "electric"),
    ),
    PokemonType.DARK: DefensiveTraits(
        weaknesses=_types("fighting", "fairy", "bug"),
        resistances=_types("ghost", "dark"),
        immunities=_types("psychic"),
    ),
    PokemonType.FAIRY: DefensiveTraits(
        weaknesses=_types("poison", "steel"),
        resistances=_types("fighting", "bug", "dark"),
        immunities=_types("dragon"),
    ),
}


TYPE_ALIASES: Final[dict[str, PokemonType]] = {
    **{pokemon_type.value: pokemon_type for pokemon_type in PokemonType},
    "一般": PokemonType.NORMAL,
    "格鬥": PokemonType.FIGHTING,
    "飛行": PokemonType.FLYING,
    "毒": PokemonType.POISON,
    "地面": PokemonType.GROUND,
    "岩石": PokemonType.ROCK,
    "蟲": PokemonType.BUG,
    "幽靈": PokemonType.GHOST,
    "鋼": PokemonType.STEEL,
    "火": PokemonType.FIRE,
    "水": PokemonType.WATER,
    "草": PokemonType.GRASS,
    "電": PokemonType.ELECTRIC,
    "電氣": PokemonType.ELECTRIC,
    "超能力": PokemonType.PSYCHIC,
    "冰": PokemonType.ICE,
    "龍": PokemonType.DRAGON,
    "惡": PokemonType.DARK,
    "妖精": PokemonType.FAIRY,
}


def parse_type(value: str) -> PokemonType:
    """Parse English or Traditional Chinese type labels."""
    normalized = value.strip().lower()
    try:
        return TYPE_ALIASES[normalized]
    except KeyError as error:
        raise ValueError(f"unknown Pokémon type: {value!r}") from error


def single_type_effectiveness(
    attacking_type: PokemonType, defending_type: PokemonType
) -> float:
    traits = TYPE_TRAITS[defending_type]
    if attacking_type in traits.weaknesses:
        return SUPER_EFFECTIVE
    if attacking_type in traits.resistances:
        return RESISTED
    if attacking_type in traits.immunities:
        return IMMUNE
    return NEUTRAL


def effectiveness(
    attacking_type: PokemonType, defending_types: Iterable[PokemonType]
) -> float:
    """Return the stacked damage multiplier against one or two types."""
    types = tuple(defending_types)
    if not 1 <= len(types) <= 2:
        raise ValueError("defending_types must contain one or two types")
    if len(set(types)) != len(types):
        raise ValueError("defending types must be unique")
    return reduce(
        mul,
        (
            single_type_effectiveness(attacking_type, defending_type)
            for defending_type in types
        ),
        NEUTRAL,
    )
