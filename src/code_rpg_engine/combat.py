from __future__ import annotations

import random
from dataclasses import dataclass

from .dice import count_face, roll_combat_dice
from .models import Entity


@dataclass(frozen=True, slots=True)
class CombatResult:
    attacker_id: str
    defender_id: str
    attack_rolls: tuple[str, ...]
    defense_rolls: tuple[str, ...]
    hits: int
    guards: int
    damage: int
    defender_hp: int


def resolve_melee(attacker: Entity, defender: Entity, rng: random.Random | None = None) -> CombatResult:
    if not attacker.alive or not defender.alive:
        raise ValueError("dead entities cannot fight")
    if attacker.position.manhattan(defender.position) != 1:
        raise ValueError("melee attack requires orthogonal adjacency")

    rng = rng or random.Random()
    attack_rolls = tuple(roll_combat_dice(attacker.attack_dice, rng))
    defense_rolls = tuple(roll_combat_dice(defender.defense_dice, rng))
    hits = count_face(attack_rolls, "hit")
    guards = count_face(defense_rolls, "guard")
    damage = max(0, hits - guards)
    defender.take_damage(damage)

    return CombatResult(
        attacker_id=attacker.id,
        defender_id=defender.id,
        attack_rolls=attack_rolls,
        defense_rolls=defense_rolls,
        hits=hits,
        guards=guards,
        damage=damage,
        defender_hp=defender.hp,
    )
