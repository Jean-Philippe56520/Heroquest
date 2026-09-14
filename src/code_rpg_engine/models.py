from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class Position:
    x: int
    y: int

    def manhattan(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)


class Team(str, Enum):
    HERO = "hero"
    MONSTER = "monster"


@dataclass(slots=True)
class Entity:
    id: str
    name: str
    position: Position
    team: Team
    max_hp: int
    hp: int
    attack_dice: int
    defense_dice: int
    move_points: int = 6
    tags: set[str] = field(default_factory=set)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        amount = max(0, amount)
        before = self.hp
        self.hp = max(0, self.hp - amount)
        return before - self.hp


@dataclass(slots=True)
class Door:
    id: str
    position: Position
    open: bool = False
    locked: bool = False


@dataclass(slots=True)
class Trap:
    id: str
    position: Position
    damage: int = 1
    revealed: bool = False
    disarmed: bool = False


@dataclass(slots=True)
class Chest:
    id: str
    position: Position
    loot: list[dict[str, Any]] = field(default_factory=list)
    opened: bool = False
