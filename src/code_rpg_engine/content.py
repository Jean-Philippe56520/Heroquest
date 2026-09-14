from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .board import Board
from .models import Chest, Door, Entity, Position, Team, Trap, Zone


@dataclass(slots=True)
class Quest:
    id: str
    title: str
    description: str
    board: Board
    entities: dict[str, Entity]
    objectives: list[str]
    metadata: dict[str, Any]


def _pos(raw: list[int]) -> Position:
    if len(raw) != 2:
        raise ValueError("position must contain [x, y]")
    return Position(int(raw[0]), int(raw[1]))


def load_quest(path: str | Path) -> Quest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    board_data = payload["board"]
    board = Board(
        width=int(board_data["width"]),
        height=int(board_data["height"]),
        walls={_pos(value) for value in board_data.get("walls", [])},
    )

    for raw in board_data.get("doors", []):
        secret = bool(raw.get("secret", False))
        door = Door(
            id=raw["id"],
            position=_pos(raw["position"]),
            open=bool(raw.get("open", False)),
            locked=bool(raw.get("locked", False)),
            secret=secret,
            revealed=bool(raw.get("revealed", not secret)),
        )
        board.doors[door.id] = door

    for raw in board_data.get("traps", []):
        trap = Trap(
            id=raw["id"],
            position=_pos(raw["position"]),
            damage=int(raw.get("damage", 1)),
            revealed=bool(raw.get("revealed", False)),
            disarmed=bool(raw.get("disarmed", False)),
        )
        board.traps[trap.id] = trap

    for raw in board_data.get("chests", []):
        chest = Chest(
            id=raw["id"],
            position=_pos(raw["position"]),
            loot=list(raw.get("loot", [])),
            opened=bool(raw.get("opened", False)),
        )
        board.chests[chest.id] = chest

    for raw in board_data.get("zones", []):
        zone = Zone(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            tiles={_pos(value) for value in raw.get("tiles", [])},
            kind=raw.get("kind", "room"),
        )
        board.zones[zone.id] = zone

    entities: dict[str, Entity] = {}
    for raw in payload.get("entities", []):
        entity = Entity(
            id=raw["id"],
            name=raw["name"],
            position=_pos(raw["position"]),
            team=Team(raw["team"]),
            max_hp=int(raw["max_hp"]),
            hp=int(raw.get("hp", raw["max_hp"])),
            attack_dice=int(raw.get("attack_dice", 1)),
            defense_dice=int(raw.get("defense_dice", 1)),
            move_points=int(raw.get("move_points", 6)),
            tags=set(raw.get("tags", [])),
            xp=int(raw.get("xp", 0)),
            level=int(raw.get("level", 1)),
            gold=int(raw.get("gold", 0)),
            xp_reward=int(raw.get("xp_reward", 1)),
            inventory=list(raw.get("inventory", [])),
            equipment=dict(raw.get("equipment", {})),
        )
        if entity.id in entities:
            raise ValueError(f"duplicate entity id: {entity.id}")
        if not board.in_bounds(entity.position):
            raise ValueError(f"entity {entity.id} starts out of bounds")
        entities[entity.id] = entity

    return Quest(
        id=payload["id"],
        title=payload["title"],
        description=payload.get("description", ""),
        board=board,
        entities=entities,
        objectives=list(payload.get("objectives", [])),
        metadata=dict(payload.get("metadata", {})),
    )
