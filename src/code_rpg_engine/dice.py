from __future__ import annotations

import random
from collections.abc import Sequence

COMBAT_DIE: tuple[str, ...] = ("hit", "hit", "hit", "guard", "guard", "blank")


def roll_combat_dice(count: int, rng: random.Random | None = None) -> list[str]:
    if count < 0:
        raise ValueError("count must be >= 0")
    rng = rng or random.Random()
    return [rng.choice(COMBAT_DIE) for _ in range(count)]


def count_face(rolls: Sequence[str], face: str) -> int:
    return sum(1 for value in rolls if value == face)
