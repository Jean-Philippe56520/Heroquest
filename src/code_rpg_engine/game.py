from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .combat import CombatResult, resolve_melee
from .content import Quest
from .models import Entity, Position, Team


class RuleError(RuntimeError):
    pass


@dataclass(slots=True)
class Game:
    quest: Quest
    rng: random.Random = field(default_factory=random.Random)
    round_number: int = 1
    active_team: Team = Team.HERO
    explored_tiles: set[Position] = field(default_factory=set)
    discovered_zone_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.refresh_exploration(emit_events=False)

    @property
    def entities(self) -> dict[str, Entity]:
        return self.quest.entities

    def current_visible_tiles(self) -> set[Position]:
        visible: set[Position] = set()
        for hero in self.entities.values():
            if hero.team != Team.HERO or not hero.alive:
                continue
            visible.update(self.quest.board.visible_tiles(hero.position, radius=2))
            zone = self.quest.board.zone_at(hero.position)
            if zone is not None:
                visible.update(zone.tiles)
        return visible

    def entity(self, entity_id: str) -> Entity:
        try:
            return self.entities[entity_id]
        except KeyError as exc:
            raise RuleError(f"unknown entity: {entity_id}") from exc

    def refresh_exploration(self, *, emit_events: bool = True) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for hero in self.entities.values():
            if hero.team != Team.HERO or not hero.alive:
                continue

            self.explored_tiles.update(self.quest.board.visible_tiles(hero.position, radius=2))
            zone = self.quest.board.zone_at(hero.position)
            if zone is not None:
                first_discovery = zone.id not in self.discovered_zone_ids
                self.discovered_zone_ids.add(zone.id)
                self.explored_tiles.update(zone.tiles)
                if emit_events and first_discovery:
                    events.append({"type": "ZoneDiscovered", "zone_id": zone.id, "name": zone.name})
        return events

    def move(self, entity_id: str, destination: Position) -> dict:
        actor = self.entity(entity_id)
        if not actor.alive:
            raise RuleError("dead entity cannot move")
        if actor.team != self.active_team:
            raise RuleError("entity does not belong to active team")
        if actor.position.manhattan(destination) != 1:
            raise RuleError("movement is one orthogonal tile per action")
        if not self.quest.board.is_walkable(destination, self.entities, mover_id=entity_id):
            raise RuleError("destination is blocked")

        origin = actor.position
        actor.position = destination
        events: list[dict[str, Any]] = [
            {"type": "ActorMoved", "actor_id": entity_id, "from": [origin.x, origin.y], "to": [destination.x, destination.y]}
        ]

        trap = self.quest.board.trap_at(destination)
        if trap and not trap.disarmed:
            trap.revealed = True
            dealt = actor.take_damage(trap.damage)
            events.append({"type": "TrapTriggered", "trap_id": trap.id, "actor_id": entity_id, "damage": dealt})

        if actor.team == Team.HERO:
            events.extend(self.refresh_exploration())

        return {"ok": True, "events": events}

    def open_door(self, entity_id: str, door_id: str) -> dict:
        actor = self.entity(entity_id)
        door = self.quest.board.doors.get(door_id)
        if door is None:
            raise RuleError("unknown door")
        if actor.team != self.active_team:
            raise RuleError("entity does not belong to active team")
        if actor.position.manhattan(door.position) > 1:
            raise RuleError("door is not adjacent")
        if door.secret and not door.revealed:
            raise RuleError("secret door has not been discovered")
        if door.locked:
            raise RuleError("door is locked")
        door.open = True
        events: list[dict[str, Any]] = [{"type": "DoorOpened", "door_id": door.id, "actor_id": actor.id}]
        if actor.team == Team.HERO:
            events.extend(self.refresh_exploration())
        return {"ok": True, "events": events}

    def search_secret_doors(self, entity_id: str, radius: int = 1) -> list[str]:
        actor = self.entity(entity_id)
        if actor.team != Team.HERO:
            raise RuleError("only heroes can search for secret doors")
        revealed: list[str] = []
        for door in self.quest.board.doors.values():
            if door.secret and not door.revealed and actor.position.manhattan(door.position) <= radius:
                door.revealed = True
                revealed.append(door.id)
                self.explored_tiles.add(door.position)
        return revealed

    def attack(self, attacker_id: str, defender_id: str) -> CombatResult:
        attacker = self.entity(attacker_id)
        defender = self.entity(defender_id)
        if attacker.team != self.active_team:
            raise RuleError("attacker does not belong to active team")
        if attacker.team == defender.team:
            raise RuleError("friendly fire is disabled")

        was_alive = defender.alive
        try:
            result = resolve_melee(attacker, defender, self.rng)
        except ValueError as exc:
            raise RuleError(str(exc)) from exc

        if was_alive and not defender.alive and attacker.team == Team.HERO:
            self.gain_xp(attacker.id, defender.xp_reward)
        return result

    def reveal_traps(self, entity_id: str) -> list[str]:
        actor = self.entity(entity_id)
        revealed: list[str] = []
        for trap in self.quest.board.traps.values():
            if not trap.disarmed and actor.position.manhattan(trap.position) <= 1:
                trap.revealed = True
                revealed.append(trap.id)
        return revealed

    def disarm_trap(self, entity_id: str, trap_id: str) -> dict:
        actor = self.entity(entity_id)
        trap = self.quest.board.traps.get(trap_id)
        if trap is None:
            raise RuleError("unknown trap")
        if actor.position.manhattan(trap.position) > 1:
            raise RuleError("trap is not adjacent")
        if not trap.revealed:
            raise RuleError("trap must be revealed first")
        trap.disarmed = True
        return {"ok": True, "events": [{"type": "TrapDisarmed", "trap_id": trap.id, "actor_id": actor.id}]}

    def open_chest(self, entity_id: str, chest_id: str) -> dict:
        actor = self.entity(entity_id)
        chest = self.quest.board.chests.get(chest_id)
        if chest is None:
            raise RuleError("unknown chest")
        if actor.position.manhattan(chest.position) > 1:
            raise RuleError("chest is not adjacent")
        if chest.opened:
            raise RuleError("chest already opened")

        chest.opened = True
        collected: list[dict[str, Any]] = []
        gold_gained = 0
        for item in chest.loot:
            item_copy = dict(item)
            if item_copy.get("type") == "currency":
                amount = int(item_copy.get("amount", 0))
                actor.gold += amount
                gold_gained += amount
            else:
                actor.inventory.append(item_copy)
                collected.append(item_copy)

        return {
            "ok": True,
            "loot": list(chest.loot),
            "items_collected": collected,
            "gold_gained": gold_gained,
            "events": [{"type": "ChestOpened", "chest_id": chest.id, "actor_id": actor.id}],
        }

    def equip_item(self, entity_id: str, item_id: str) -> dict:
        actor = self.entity(entity_id)
        index = next((i for i, item in enumerate(actor.inventory) if item.get("id") == item_id), None)
        if index is None:
            raise RuleError("item is not in inventory")

        item = actor.inventory[index]
        slot = item.get("slot")
        if not slot:
            raise RuleError("item cannot be equipped")

        actor.inventory.pop(index)
        previous = actor.equipment.get(str(slot))
        if previous is not None:
            actor.inventory.append(previous)
        actor.equipment[str(slot)] = item
        return {
            "ok": True,
            "events": [{"type": "ItemEquipped", "actor_id": actor.id, "item_id": item_id, "slot": str(slot)}],
        }

    def gain_xp(self, entity_id: str, amount: int) -> dict:
        actor = self.entity(entity_id)
        if amount < 0:
            raise RuleError("xp gain cannot be negative")
        actor.xp += amount
        levels_gained = 0
        while actor.xp >= actor.next_level_xp:
            threshold = actor.next_level_xp
            actor.xp -= threshold
            actor.level += 1
            actor.max_hp += 1
            actor.hp = min(actor.max_hp, actor.hp + 1)
            levels_gained += 1
        return {"ok": True, "xp_gained": amount, "levels_gained": levels_gained, "level": actor.level}

    def end_team_turn(self) -> Team:
        if self.active_team == Team.HERO:
            self.active_team = Team.MONSTER
        else:
            self.active_team = Team.HERO
            self.round_number += 1
        return self.active_team
