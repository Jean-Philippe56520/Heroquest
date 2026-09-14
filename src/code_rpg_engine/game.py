from __future__ import annotations

import random
from dataclasses import dataclass, field

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

    @property
    def entities(self) -> dict[str, Entity]:
        return self.quest.entities

    def entity(self, entity_id: str) -> Entity:
        try:
            return self.entities[entity_id]
        except KeyError as exc:
            raise RuleError(f"unknown entity: {entity_id}") from exc

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
        events = [{"type": "ActorMoved", "actor_id": entity_id, "from": [origin.x, origin.y], "to": [destination.x, destination.y]}]

        trap = self.quest.board.trap_at(destination)
        if trap and not trap.disarmed:
            trap.revealed = True
            dealt = actor.take_damage(trap.damage)
            events.append({"type": "TrapTriggered", "trap_id": trap.id, "actor_id": entity_id, "damage": dealt})

        return {"ok": True, "events": events}

    def open_door(self, entity_id: str, door_id: str) -> dict:
        actor = self.entity(entity_id)
        door = self.quest.board.doors.get(door_id)
        if door is None:
            raise RuleError("unknown door")
        if actor.position.manhattan(door.position) > 1:
            raise RuleError("door is not adjacent")
        if door.locked:
            raise RuleError("door is locked")
        door.open = True
        return {"ok": True, "events": [{"type": "DoorOpened", "door_id": door.id, "actor_id": actor.id}]}

    def attack(self, attacker_id: str, defender_id: str) -> CombatResult:
        attacker = self.entity(attacker_id)
        defender = self.entity(defender_id)
        if attacker.team != self.active_team:
            raise RuleError("attacker does not belong to active team")
        if attacker.team == defender.team:
            raise RuleError("friendly fire is disabled")
        try:
            return resolve_melee(attacker, defender, self.rng)
        except ValueError as exc:
            raise RuleError(str(exc)) from exc

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
        return {
            "ok": True,
            "loot": list(chest.loot),
            "events": [{"type": "ChestOpened", "chest_id": chest.id, "actor_id": actor.id}],
        }

    def end_team_turn(self) -> Team:
        if self.active_team == Team.HERO:
            self.active_team = Team.MONSTER
        else:
            self.active_team = Team.HERO
            self.round_number += 1
        return self.active_team
