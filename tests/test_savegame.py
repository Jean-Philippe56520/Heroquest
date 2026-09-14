import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from code_rpg_engine.content import load_quest
from code_rpg_engine.game import Game
from code_rpg_engine.models import Position, Team
from code_rpg_engine.savegame import SaveGameError, build_save, dumps_save, loads_save, restore_game


class SaveGameTests(unittest.TestCase):
    def setUp(self):
        self.quest_path = ROOT / "content" / "quests" / "crypt_of_echoes.json"

    def make_progressed_game(self) -> Game:
        game = Game(load_quest(self.quest_path), rng=random.Random(7))
        hero = game.entity("hero-warden")
        game.move(hero.id, Position(2, 2))
        game.open_door(hero.id, "door-crypt")
        game.move(hero.id, Position(3, 2))
        game.move(hero.id, Position(4, 2))
        game.move(hero.id, Position(4, 1))
        game.move(hero.id, Position(5, 1))
        game.reveal_traps(hero.id)
        game.disarm_trap(hero.id, "trap-needle")
        game.open_chest(hero.id, "chest-echo")
        game.equip_item(hero.id, "echo-blade")
        game.gain_xp(hero.id, 10)
        game.move(hero.id, Position(4, 1))
        game.move(hero.id, Position(4, 2))
        game.move(hero.id, Position(4, 3))
        game.move(hero.id, Position(4, 4))
        game.search_secret_doors(hero.id)
        game.entity("monster-bone-warden").take_damage(99)
        game.end_team_turn()
        return game

    def test_round_trip_restores_progress(self):
        original = self.make_progressed_game()
        text = dumps_save(
            original,
            save_id="save-test-001",
            created_at="2026-09-14T20:00:00+00:00",
            completed_quests=["tutorial"],
        )
        data = loads_save(text)
        restored = restore_game(load_quest(self.quest_path), data, rng=random.Random(99))

        self.assertEqual(data["save_id"], "save-test-001")
        self.assertEqual(data["created_at"], "2026-09-14T20:00:00+00:00")
        self.assertEqual(restored.round_number, original.round_number)
        self.assertEqual(restored.active_team, Team.MONSTER)
        self.assertEqual(restored.explored_tiles, original.explored_tiles)
        self.assertEqual(restored.discovered_zone_ids, original.discovered_zone_ids)

        for entity_id in original.entities:
            before = original.entity(entity_id)
            after = restored.entity(entity_id)
            self.assertEqual(after.position, before.position)
            self.assertEqual(after.hp, before.hp)
            self.assertEqual(after.max_hp, before.max_hp)

        before_hero = original.entity("hero-warden")
        after_hero = restored.entity("hero-warden")
        self.assertEqual(after_hero.level, before_hero.level)
        self.assertEqual(after_hero.xp, before_hero.xp)
        self.assertEqual(after_hero.gold, 25)
        self.assertEqual(after_hero.inventory, before_hero.inventory)
        self.assertEqual(after_hero.equipment, before_hero.equipment)
        self.assertEqual(after_hero.equipment["weapon"]["id"], "echo-blade")

        self.assertTrue(restored.quest.board.doors["door-crypt"].open)
        self.assertTrue(restored.quest.board.doors["door-secret"].revealed)
        self.assertTrue(restored.quest.board.traps["trap-needle"].disarmed)
        self.assertTrue(restored.quest.board.chests["chest-echo"].opened)
        self.assertFalse(restored.entity("monster-bone-warden").alive)

    def test_build_save_is_json_serializable(self):
        data = build_save(Game(load_quest(self.quest_path)))
        encoded = json.dumps(data)
        self.assertIn("schema_version", encoded)

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(SaveGameError):
            loads_save(b"{not-json")

    def test_unknown_schema_is_rejected(self):
        data = build_save(Game(load_quest(self.quest_path)))
        data["schema_version"] = 99
        with self.assertRaises(SaveGameError):
            loads_save(json.dumps(data))

    def test_wrong_quest_is_rejected(self):
        data = build_save(Game(load_quest(self.quest_path)))
        data["quest_id"] = "another-quest"
        data["campaign"]["current_quest"] = "another-quest"
        with self.assertRaises(SaveGameError):
            restore_game(load_quest(self.quest_path), data)

    def test_unknown_hero_is_rejected_without_mutating_source_quest(self):
        quest = load_quest(self.quest_path)
        original_position = quest.entities["hero-warden"].position
        data = build_save(Game(load_quest(self.quest_path)))
        data["heroes"]["intruder"] = data["heroes"].pop("hero-warden")
        with self.assertRaises(SaveGameError):
            restore_game(quest, data)
        self.assertEqual(quest.entities["hero-warden"].position, original_position)


if __name__ == "__main__":
    unittest.main()
