from __future__ import annotations

from dataclasses import dataclass, field

from .models import Chest, Door, Entity, Position, Trap, Zone


@dataclass(slots=True)
class Board:
    width: int
    height: int
    walls: set[Position] = field(default_factory=set)
    doors: dict[str, Door] = field(default_factory=dict)
    traps: dict[str, Trap] = field(default_factory=dict)
    chests: dict[str, Chest] = field(default_factory=dict)
    zones: dict[str, Zone] = field(default_factory=dict)

    def in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def door_at(self, pos: Position) -> Door | None:
        return next((door for door in self.doors.values() if door.position == pos), None)

    def trap_at(self, pos: Position) -> Trap | None:
        return next((trap for trap in self.traps.values() if trap.position == pos), None)

    def chest_at(self, pos: Position) -> Chest | None:
        return next((chest for chest in self.chests.values() if chest.position == pos), None)

    def zone_at(self, pos: Position) -> Zone | None:
        return next((zone for zone in self.zones.values() if pos in zone.tiles), None)

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

    def visible_tiles(self, origin: Position, radius: int = 2) -> set[Position]:
        """Return nearby tiles using a small flood fill blocked by walls/closed doors.

        Blocking tiles themselves are visible, but vision does not continue through them.
        Rooms are revealed separately by Game when a hero enters a named zone.
        """
        visible: set[Position] = {origin}
        frontier: list[tuple[Position, int]] = [(origin, 0)]
        seen: set[Position] = {origin}

        while frontier:
            current, distance = frontier.pop(0)
            if distance >= radius:
                continue
            for candidate in self.neighbors(current):
                if candidate in seen:
                    continue
                seen.add(candidate)
                visible.add(candidate)
                door = self.door_at(candidate)
                blocked = candidate in self.walls or (door is not None and not door.open)
                if not blocked:
                    frontier.append((candidate, distance + 1))
        return visible
