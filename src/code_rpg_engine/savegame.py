from __future__ import annotations

import json
import random
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .content import Quest
from .game import Game
from .models import Entity, Position, Team

SAVE_SCHEMA_VERSION = 1
DEFAULT_CAMPAIGN_ID = "main-campaign"
MAX_SAVE_BYTES = 1_000_000


class SaveGameError(ValueError):
    """Raised when a save file is malformed, incompatible, or unsafe to apply."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _position_data(position: Position) -> list[int]:
    return [position.x, position.y]


def _sorted_positions(positions: set[Position]) -> list[list[int]]:
    return [[pos.x, pos.y] for pos in sorted(positions, key=lambda item: (item.y, item.x))]


def _hero_state(hero: Entity) -> dict[str, Any]:
    return {
        "name": hero.name,
        "position": _position_data(hero.position),
        "hp": hero.hp,
        "max_hp": hero.max_hp,
        "attack_dice": hero.attack_dice,
        "defense_dice": hero.defense_dice,
        "move_points": hero.move_points,
        "tags": sorted(hero.tags),
        "xp": hero.xp,
        "level": hero.level,
        "gold": hero.gold,
        "inventory": deepcopy(hero.inventory),
        "equipment": deepcopy(hero.equipment),
    }


def _entity_state(entity: Entity) -> dict[str, Any]:
    return {
        "position": _position_data(entity.position),
        "hp": entity.hp,
        "max_hp": entity.max_hp,
    }


def build_save(
    game: Game,
    *,
    save_id: str | None = None,
    created_at: str | None = None,
    campaign_id: str = DEFAULT_CAMPAIGN_ID,
    completed_quests: list[str] | None = None,
) -> dict[str, Any]:
    """Serialize dynamic game state into a versioned, JSON-safe document."""
    now = _utc_now()
    heroes = {
        entity.id: _hero_state(entity)
        for entity in game.entities.values()
        if entity.team == Team.HERO
    }
    other_entities = {
        entity.id: _entity_state(entity)
        for entity in game.entities.values()
        if entity.team != Team.HERO
    }
    board = game.quest.board
    return {
        "schema_version": SAVE_SCHEMA_VERSION,
        "save_id": save_id or str(uuid.uuid4()),
        "created_at": created_at or now,
        "updated_at": now,
        "quest_id": game.quest.id,
        "quest_schema_version": int(game.quest.metadata.get("schema_version", 1)),
        "campaign": {
            "campaign_id": campaign_id,
            "current_quest": game.quest.id,
            "completed_quests": list(completed_quests or []),
        },
        "heroes": heroes,
        "entities": other_entities,
        "quest_state": {
            "round_number": game.round_number,
            "active_team": game.active_team.value,
            "explored_tiles": _sorted_positions(game.explored_tiles),
            "discovered_zone_ids": sorted(game.discovered_zone_ids),
            "doors": {
                door_id: {
                    "open": door.open,
                    "locked": door.locked,
                    "revealed": door.revealed,
                }
                for door_id, door in board.doors.items()
            },
            "traps": {
                trap_id: {
                    "revealed": trap.revealed,
                    "disarmed": trap.disarmed,
                }
                for trap_id, trap in board.traps.items()
            },
            "chests": {
                chest_id: {"opened": chest.opened}
                for chest_id, chest in board.chests.items()
            },
        },
    }


def dumps_save(game: Game, **kwargs: Any) -> str:
    return json.dumps(build_save(game, **kwargs), ensure_ascii=False, indent=2, sort_keys=True)


def migrate_save(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy migrated to the current save schema.

    Schema 1 is the first public format. Future migrations should be chained here.
    """
    migrated = deepcopy(data)
    version = migrated.get("schema_version")
    if version != SAVE_SCHEMA_VERSION:
        raise SaveGameError(f"unsupported save schema version: {version!r}")
    return migrated


def validate_save(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise SaveGameError("save root must be a JSON object")
    required = {
        "schema_version",
        "save_id",
        "created_at",
        "updated_at",
        "quest_id",
        "campaign",
        "heroes",
        "entities",
        "quest_state",
    }
    missing = sorted(required - set(data))
    if missing:
        raise SaveGameError(f"missing save fields: {', '.join(missing)}")
    if data["schema_version"] != SAVE_SCHEMA_VERSION:
        raise SaveGameError(f"unsupported save schema version: {data['schema_version']!r}")
    if not isinstance(data["save_id"], str) or not data["save_id"].strip():
        raise SaveGameError("save_id must be a non-empty string")
    if not isinstance(data["quest_id"], str) or not data["quest_id"].strip():
        raise SaveGameError("quest_id must be a non-empty string")
    for timestamp in ("created_at", "updated_at"):
        if not isinstance(data[timestamp], str) or not data[timestamp].strip():
            raise SaveGameError(f"{timestamp} must be a non-empty string")
    for field_name in ("campaign", "heroes", "entities", "quest_state"):
        if not isinstance(data[field_name], dict):
            raise SaveGameError(f"{field_name} must be an object")
    campaign = data["campaign"]
    if campaign.get("current_quest") != data["quest_id"]:
        raise SaveGameError("campaign current_quest must match quest_id")
    quest_state = data["quest_state"]
    if not isinstance(quest_state.get("round_number"), int) or quest_state["round_number"] < 1:
        raise SaveGameError("round_number must be a positive integer")
    try:
        Team(quest_state.get("active_team"))
    except (TypeError, ValueError) as exc:
        raise SaveGameError("active_team is invalid") from exc
    for key in ("explored_tiles", "discovered_zone_ids"):
        if not isinstance(quest_state.get(key), list):
            raise SaveGameError(f"{key} must be a list")
    for key in ("doors", "traps", "chests"):
        if not isinstance(quest_state.get(key), dict):
            raise SaveGameError(f"{key} must be an object")


def loads_save(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, bytes) and len(raw) > MAX_SAVE_BYTES:
        raise SaveGameError("save file is too large")
    if isinstance(raw, str) and len(raw.encode("utf-8")) > MAX_SAVE_BYTES:
        raise SaveGameError("save file is too large")
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SaveGameError("save is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise SaveGameError("save root must be a JSON object")
    migrated = migrate_save(data)
    validate_save(migrated)
    return migrated


def _position(value: Any, *, label: str) -> Position:
    if not isinstance(value, list) or len(value) != 2:
        raise SaveGameError(f"{label} must be [x, y]")
    try:
        return Position(int(value[0]), int(value[1]))
    except (TypeError, ValueError) as exc:
        raise SaveGameError(f"{label} must contain integers") from exc


def _non_negative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise SaveGameError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SaveGameError(f"{label} must be an integer") from exc
    if parsed < 0:
        raise SaveGameError(f"{label} must be >= 0")
    return parsed


def _apply_hero_state(entity: Entity, state: dict[str, Any], game: Game) -> None:
    if not isinstance(state, dict):
        raise SaveGameError(f"hero state for {entity.id} must be an object")
    position = _position(state.get("position"), label=f"hero {entity.id} position")
    if not game.quest.board.in_bounds(position):
        raise SaveGameError(f"hero {entity.id} position is out of bounds")
    max_hp = _non_negative_int(state.get("max_hp"), label=f"hero {entity.id} max_hp")
    if max_hp < 1:
        raise SaveGameError(f"hero {entity.id} max_hp must be >= 1")
    hp = _non_negative_int(state.get("hp"), label=f"hero {entity.id} hp")
    if hp > max_hp:
        raise SaveGameError(f"hero {entity.id} hp exceeds max_hp")
    level = _non_negative_int(state.get("level"), label=f"hero {entity.id} level")
    if level < 1:
        raise SaveGameError(f"hero {entity.id} level must be >= 1")
    inventory = state.get("inventory")
    equipment = state.get("equipment")
    tags = state.get("tags")
    if not isinstance(inventory, list) or not all(isinstance(item, dict) for item in inventory):
        raise SaveGameError(f"hero {entity.id} inventory must be a list of objects")
    if not isinstance(equipment, dict) or not all(isinstance(item, dict) for item in equipment.values()):
        raise SaveGameError(f"hero {entity.id} equipment must be an object of items")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise SaveGameError(f"hero {entity.id} tags must be a list of strings")
    entity.name = str(state.get("name", entity.name))
    entity.position = position
    entity.hp = hp
    entity.max_hp = max_hp
    entity.attack_dice = _non_negative_int(state.get("attack_dice"), label=f"hero {entity.id} attack_dice")
    entity.defense_dice = _non_negative_int(state.get("defense_dice"), label=f"hero {entity.id} defense_dice")
    entity.move_points = _non_negative_int(state.get("move_points"), label=f"hero {entity.id} move_points")
    entity.tags = set(tags)
    entity.xp = _non_negative_int(state.get("xp"), label=f"hero {entity.id} xp")
    entity.level = level
    entity.gold = _non_negative_int(state.get("gold"), label=f"hero {entity.id} gold")
    entity.inventory = deepcopy(inventory)
    entity.equipment = deepcopy(equipment)


def _apply_other_entity_state(entity: Entity, state: dict[str, Any], game: Game) -> None:
    if not isinstance(state, dict):
        raise SaveGameError(f"entity state for {entity.id} must be an object")
    position = _position(state.get("position"), label=f"entity {entity.id} position")
    if not game.quest.board.in_bounds(position):
        raise SaveGameError(f"entity {entity.id} position is out of bounds")
    max_hp = _non_negative_int(state.get("max_hp"), label=f"entity {entity.id} max_hp")
    if max_hp < 1:
        raise SaveGameError(f"entity {entity.id} max_hp must be >= 1")
    hp = _non_negative_int(state.get("hp"), label=f"entity {entity.id} hp")
    if hp > max_hp:
        raise SaveGameError(f"entity {entity.id} hp exceeds max_hp")
    entity.position = position
    entity.max_hp = max_hp
    entity.hp = hp


def restore_game(quest: Quest, save_data: dict[str, Any], *, rng: random.Random | None = None) -> Game:
    """Create a fresh game from quest data and atomically apply a validated save."""
    data = migrate_save(save_data)
    validate_save(data)
    if data["quest_id"] != quest.id:
        raise SaveGameError(f"save targets quest {data['quest_id']!r}, not {quest.id!r}")

    game = Game(quest=deepcopy(quest), rng=rng or random.Random())
    hero_ids = {entity.id for entity in game.entities.values() if entity.team == Team.HERO}
    other_ids = set(game.entities) - hero_ids
    saved_hero_ids = set(data["heroes"])
    saved_other_ids = set(data["entities"])
    unknown_heroes = saved_hero_ids - hero_ids
    unknown_entities = saved_other_ids - other_ids
    if unknown_heroes:
        raise SaveGameError(f"save references unknown heroes: {', '.join(sorted(unknown_heroes))}")
    if unknown_entities:
        raise SaveGameError(f"save references unknown entities: {', '.join(sorted(unknown_entities))}")

    for entity_id, state in data["heroes"].items():
        _apply_hero_state(game.entities[entity_id], state, game)
    for entity_id, state in data["entities"].items():
        _apply_other_entity_state(game.entities[entity_id], state, game)

    quest_state = data["quest_state"]
    game.round_number = int(quest_state["round_number"])
    game.active_team = Team(quest_state["active_team"])
    game.explored_tiles = {
        _position(value, label="explored tile") for value in quest_state["explored_tiles"]
    }
    if any(not game.quest.board.in_bounds(pos) for pos in game.explored_tiles):
        raise SaveGameError("explored tile is out of bounds")
    game.discovered_zone_ids = set(quest_state["discovered_zone_ids"])
    unknown_zones = game.discovered_zone_ids - set(game.quest.board.zones)
    if unknown_zones:
        raise SaveGameError(f"save references unknown zones: {', '.join(sorted(unknown_zones))}")

    for collection_name, target in (
        ("doors", game.quest.board.doors),
        ("traps", game.quest.board.traps),
        ("chests", game.quest.board.chests),
    ):
        saved_ids = set(quest_state[collection_name])
        unknown_ids = saved_ids - set(target)
        if unknown_ids:
            raise SaveGameError(f"save references unknown {collection_name}: {', '.join(sorted(unknown_ids))}")

    for door_id, state in quest_state["doors"].items():
        if not isinstance(state, dict):
            raise SaveGameError(f"door state for {door_id} must be an object")
        door = game.quest.board.doors[door_id]
        door.open = bool(state.get("open", False))
        door.locked = bool(state.get("locked", False))
        door.revealed = bool(state.get("revealed", door.revealed))
    for trap_id, state in quest_state["traps"].items():
        if not isinstance(state, dict):
            raise SaveGameError(f"trap state for {trap_id} must be an object")
        trap = game.quest.board.traps[trap_id]
        trap.revealed = bool(state.get("revealed", False))
        trap.disarmed = bool(state.get("disarmed", False))
    for chest_id, state in quest_state["chests"].items():
        if not isinstance(state, dict):
            raise SaveGameError(f"chest state for {chest_id} must be an object")
        game.quest.board.chests[chest_id].opened = bool(state.get("opened", False))

    occupied: set[Position] = set()
    for entity in game.entities.values():
        if not entity.alive:
            continue
        if entity.position in game.quest.board.walls:
            raise SaveGameError(f"alive entity {entity.id} cannot stand in a wall")
        door = game.quest.board.door_at(entity.position)
        if door is not None and not door.open:
            raise SaveGameError(f"alive entity {entity.id} cannot stand in a closed door")
        if entity.position in occupied:
            raise SaveGameError("two living entities cannot occupy the same tile")
        occupied.add(entity.position)

    return game
