from __future__ import annotations

from dataclasses import dataclass, field

from .models import Chest, Door, Entity, Position, Trap


@dataclass(slots=True)
class Board:
    width: int
    height: int
    walls: set[Position] = field(default_factory=set)
    doors: dict[str, Door] = field(default_factory=dict)
    traps: dict[str, Trap] = field(default_factory=dict)
    chests: dict[str, Chest] = field(default_factory=dict)

    def in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def door_at(self, pos: Position) -> Door | None:
        return next((door for door in self.doors.values() if door.position == pos), None)

    def trap_at(self, pos: Position) -> Trap | None:
        return next((trap for trap in self.traps.values() if trap.position == pos), None)

    def chest_at(self, pos: Position) -> Chest | None:
        return next((chest for chest in self.chests.values() if chest.position == pos), None)

    def is_walkable(self, pos: Position, entities: dict[str, Entity], mover_id: str | None = None) -> bool:
        if not self.in_bounds(pos) or pos in self.walls:
            return False

        door = self.door_at(pos)
        if door and not door.open:
            return False

        for entity in entities.values():
            if entity.id != mover_id and entity.alive and entity.position == pos:
                return False

        return True

    def neighbors(self, pos: Position) -> list[Position]:
        candidates = [
            Position(pos.x + 1, pos.y),
            Position(pos.x - 1, pos.y),
            Position(pos.x, pos.y + 1),
            Position(pos.x, pos.y - 1),
        ]
        return [candidate for candidate in candidates if self.in_bounds(candidate)]
