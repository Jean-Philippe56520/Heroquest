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
    xp: int = 0
    level: int = 1
    gold: int = 0
    xp_reward: int = 1
    inventory: list[dict[str, Any]] = field(default_factory=list)
    equipment: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def effective_attack_dice(self) -> int:
        bonus = sum(int(item.get("attack_bonus", 0)) for item in self.equipment.values())
        return max(0, self.attack_dice + bonus)

    @property
    def effective_defense_dice(self) -> int:
        bonus = sum(int(item.get("defense_bonus", 0)) for item in self.equipment.values())
        return max(0, self.defense_dice + bonus)

    @property
    def next_level_xp(self) -> int:
        return self.level * 10

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
    secret: bool = False
    revealed: bool = True

    @property
    def visible(self) -> bool:
        return not self.secret or self.revealed


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


@dataclass(slots=True)
class Zone:
    id: str
    name: str
    tiles: set[Position] = field(default_factory=set)
    kind: str = "room"
