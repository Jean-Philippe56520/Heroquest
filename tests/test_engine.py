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
from code_rpg_engine.models import Chest, Door, Entity, Position, Team, Trap, Zone


class BoardTests(unittest.TestCase):
    def test_walkability_respects_walls_and_entities(self):
        board = Board(width=4, height=4, walls={Position(2, 2)})
        hero = Entity("h", "Hero", Position(1, 1), Team.HERO, 5, 5, 2, 2)
        monster = Entity("m", "Monster", Position(1, 2), Team.MONSTER, 2, 2, 1, 1)
        entities = {hero.id: hero, monster.id: monster}
        self.assertFalse(board.is_walkable(Position(2, 2), entities, mover_id="h"))
        self.assertFalse(board.is_walkable(Position(1, 2), entities, mover_id="h"))
        self.assertTrue(board.is_walkable(Position(2, 1), entities, mover_id="h"))

    def test_visibility_stops_at_closed_door(self):
        board = Board(width=5, height=1)
        board.doors["d"] = Door("d", Position(2, 0), open=False)
        visible = board.visible_tiles(Position(0, 0), radius=4)
        self.assertIn(Position(2, 0), visible)
        self.assertNotIn(Position(3, 0), visible)


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

    def test_equipment_bonus_is_used_by_combat_stats(self):
        hero = Entity("h", "Hero", Position(0, 0), Team.HERO, 5, 5, 2, 2)
        hero.equipment["weapon"] = {"id": "blade", "attack_bonus": 1}
        self.assertEqual(hero.effective_attack_dice, 3)


class GameTests(unittest.TestCase):
    def setUp(self):
        board = Board(width=5, height=5)
        board.doors["d"] = Door("d", Position(2, 1), open=False)
        board.traps["t"] = Trap("t", Position(1, 2), damage=1)
        board.chests["c"] = Chest(
            "c",
            Position(0, 1),
            loot=[
                {"id": "blade", "name": "Blade", "type": "equipment", "slot": "weapon", "attack_bonus": 1},
                {"id": "gold", "type": "currency", "amount": 5},
            ],
        )
        board.zones["start"] = Zone("start", "Start", {Position(1, 1), Position(1, 2)})
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

    def test_chest_moves_loot_to_hero_state(self):
        result = self.game.open_chest("h", "c")
        hero = self.game.entity("h")
        self.assertEqual(hero.gold, 5)
        self.assertEqual(hero.inventory[0]["id"], "blade")
        self.assertEqual(result["gold_gained"], 5)
        with self.assertRaises(RuleError):
            self.game.open_chest("h", "c")

    def test_item_can_be_equipped(self):
        self.game.open_chest("h", "c")
        self.game.equip_item("h", "blade")
        hero = self.game.entity("h")
        self.assertEqual(hero.equipment["weapon"]["id"], "blade")
        self.assertEqual(hero.effective_attack_dice, 3)

    def test_secret_door_must_be_found_before_opening(self):
        secret = Door("s", Position(2, 1), secret=True, revealed=False)
        self.game.quest.board.doors["s"] = secret
        del self.game.quest.board.doors["d"]
        with self.assertRaises(RuleError):
            self.game.open_door("h", "s")
        found = self.game.search_secret_doors("h")
        self.assertEqual(found, ["s"])
        self.game.open_door("h", "s")
        self.assertTrue(secret.open)

    def test_zone_is_discovered_and_revealed(self):
        self.assertIn("start", self.game.discovered_zone_ids)
        self.assertIn(Position(1, 2), self.game.explored_tiles)

    def test_xp_can_level_up_hero(self):
        hero = self.game.entity("h")
        result = self.game.gain_xp("h", 10)
        self.assertEqual(result["levels_gained"], 1)
        self.assertEqual(hero.level, 2)
        self.assertEqual(hero.max_hp, 6)


class ContentTests(unittest.TestCase):
    def test_sample_quest_loads_v2_content(self):
        quest = load_quest(ROOT / "content" / "quests" / "crypt_of_echoes.json")
        self.assertEqual(quest.id, "crypt-of-echoes")
        self.assertEqual(len(quest.entities), 3)
        self.assertEqual(quest.board.width, 8)
        self.assertEqual(len(quest.board.zones), 2)
        self.assertTrue(quest.board.doors["door-secret"].secret)
        self.assertFalse(quest.board.doors["door-secret"].revealed)


if __name__ == "__main__":
    unittest.main()
