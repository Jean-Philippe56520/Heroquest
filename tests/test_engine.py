import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from code_rpg_engine.board import Board
from code_rpg_engine.combat import resolve_melee
from code_rpg_engine.content import Quest, load_quest
from code_rpg_engine.game import Game, RuleError
from code_rpg_engine.models import Chest, Door, Entity, Position, Team, Trap


class BoardTests(unittest.TestCase):
    def test_walkability_respects_walls_and_entities(self):
        board = Board(width=4, height=4, walls={Position(2, 2)})
        hero = Entity("h", "Hero", Position(1, 1), Team.HERO, 5, 5, 2, 2)
        monster = Entity("m", "Monster", Position(1, 2), Team.MONSTER, 2, 2, 1, 1)
        entities = {hero.id: hero, monster.id: monster}
        self.assertFalse(board.is_walkable(Position(2, 2), entities, mover_id="h"))
        self.assertFalse(board.is_walkable(Position(1, 2), entities, mover_id="h"))
        self.assertTrue(board.is_walkable(Position(2, 1), entities, mover_id="h"))


class CombatTests(unittest.TestCase):
    def test_melee_requires_adjacency(self):
        a = Entity("a", "A", Position(0, 0), Team.HERO, 5, 5, 3, 2)
        b = Entity("b", "B", Position(2, 0), Team.MONSTER, 5, 5, 2, 2)
        with self.assertRaises(ValueError):
            resolve_melee(a, b, random.Random(1))

    def test_melee_is_deterministic_with_seeded_rng(self):
        a = Entity("a", "A", Position(0, 0), Team.HERO, 5, 5, 3, 2)
        b = Entity("b", "B", Position(1, 0), Team.MONSTER, 5, 5, 2, 2)
        result = resolve_melee(a, b, random.Random(7))
        self.assertEqual(result.attacker_id, "a")
        self.assertGreaterEqual(result.damage, 0)
        self.assertEqual(b.hp, 5 - result.damage)


class GameTests(unittest.TestCase):
    def setUp(self):
        board = Board(width=5, height=5)
        board.doors["d"] = Door("d", Position(2, 1), open=False)
        board.traps["t"] = Trap("t", Position(1, 2), damage=1)
        board.chests["c"] = Chest("c", Position(0, 1), loot=[{"id": "gem"}])
        hero = Entity("h", "Hero", Position(1, 1), Team.HERO, 5, 5, 2, 2)
        monster = Entity("m", "Monster", Position(3, 1), Team.MONSTER, 2, 2, 1, 1)
        quest = Quest("q", "Q", "", board, {"h": hero, "m": monster}, [], {})
        self.game = Game(quest, rng=random.Random(3))

    def test_closed_door_blocks_movement_then_can_open(self):
        with self.assertRaises(RuleError):
            self.game.move("h", Position(2, 1))
        self.game.open_door("h", "d")
        result = self.game.move("h", Position(2, 1))
        self.assertTrue(result["ok"])

    def test_trap_triggers_on_entry(self):
        result = self.game.move("h", Position(1, 2))
        self.assertEqual(self.game.entity("h").hp, 4)
        self.assertEqual(result["events"][1]["type"], "TrapTriggered")

    def test_chest_can_be_opened_once(self):
        result = self.game.open_chest("h", "c")
        self.assertEqual(result["loot"], [{"id": "gem"}])
        with self.assertRaises(RuleError):
            self.game.open_chest("h", "c")


class ContentTests(unittest.TestCase):
    def test_sample_quest_loads(self):
        quest = load_quest(ROOT / "content" / "quests" / "crypt_of_echoes.json")
        self.assertEqual(quest.id, "crypt-of-echoes")
        self.assertEqual(len(quest.entities), 3)
        self.assertEqual(quest.board.width, 8)


if __name__ == "__main__":
    unittest.main()
