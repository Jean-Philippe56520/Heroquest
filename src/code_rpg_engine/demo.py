from __future__ import annotations

import argparse
import random

from .content import load_quest
from .game import Game


def main() -> None:
    parser = argparse.ArgumentParser(description="Code RPG Dungeon Engine demo")
    parser.add_argument("quest")
    args = parser.parse_args()

    quest = load_quest(args.quest)
    game = Game(quest=quest, rng=random.Random(7))

    print(f"Quest: {quest.title}")
    print(quest.description)
    print(f"Board: {quest.board.width}x{quest.board.height}")
    print("Objectives:")
    for objective in quest.objectives:
        print(f"- {objective}")
    print("Entities:")
    for entity in game.entities.values():
        print(f"- {entity.id}: {entity.name} [{entity.team.value}] hp={entity.hp} pos=({entity.position.x},{entity.position.y})")


if __name__ == "__main__":
    main()
