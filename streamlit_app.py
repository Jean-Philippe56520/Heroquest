from __future__ import annotations

import html
import random
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from code_rpg_engine.content import load_quest
from code_rpg_engine.game import Game, RuleError
from code_rpg_engine.models import Entity, Position, Team
from code_rpg_engine.savegame import SaveGameError, build_save, dumps_save, loads_save, restore_game

QUEST_PATH = ROOT / "content" / "quests" / "crypt_of_echoes.json"
QUEST_PATHS = {"crypt-of-echoes": QUEST_PATH}

st.set_page_config(page_title="Code RPG - Dungeon Engine", page_icon="⚔️", layout="wide")


def new_game() -> Game:
    quest = load_quest(QUEST_PATH)
    return Game(quest=quest, rng=random.Random())


def new_save_identity(game: Game) -> dict[str, str]:
    document = build_save(game)
    return {"save_id": document["save_id"], "created_at": document["created_at"]}


def ensure_state() -> None:
    if "game" not in st.session_state:
        st.session_state.game = new_game()
    if "selected_hero" not in st.session_state:
        st.session_state.selected_hero = "hero-warden"
    if "log" not in st.session_state:
        st.session_state.log = ["La Crypte des Échos vous attend. Explorez sans savoir ce qui se cache au-delà des murs."]
    if "save_identity" not in st.session_state:
        st.session_state.save_identity = new_save_identity(st.session_state.game)
    if "completed_quests" not in st.session_state:
        st.session_state.completed_quests = []


def reset_game() -> None:
    game = new_game()
    st.session_state.game = game
    st.session_state.selected_hero = "hero-warden"
    st.session_state.log = ["Nouvelle expédition commencée."]
    st.session_state.save_identity = new_save_identity(game)
    st.session_state.completed_quests = []


def load_uploaded_save(raw: bytes) -> None:
    data = loads_save(raw)
    quest_path = QUEST_PATHS.get(data["quest_id"])
    if quest_path is None:
        raise SaveGameError(f"quête inconnue dans cette version : {data['quest_id']}")

    quest = load_quest(quest_path)
    restored = restore_game(quest, data, rng=random.Random())
    heroes = [entity for entity in restored.entities.values() if entity.team == Team.HERO]
    living = [hero for hero in heroes if hero.alive]
    selected = (living or heroes)[0].id if heroes else None
    if selected is None:
        raise SaveGameError("la sauvegarde ne contient aucun héros compatible")

    # Session state is replaced only after the complete save has been validated.
    st.session_state.game = restored
    st.session_state.selected_hero = selected
    st.session_state.save_identity = {
        "save_id": data["save_id"],
        "created_at": data["created_at"],
    }
    st.session_state.completed_quests = list(data["campaign"].get("completed_quests", []))
    st.session_state.log = [f"Sauvegarde {data['save_id'][:8]} chargée."]


def log(message: str) -> None:
    st.session_state.log.insert(0, message)
    del st.session_state.log[50:]


def hero_entities(game: Game) -> list[Entity]:
    return [entity for entity in game.entities.values() if entity.team == Team.HERO]


def monster_entities(game: Game) -> list[Entity]:
    return [entity for entity in game.entities.values() if entity.team == Team.MONSTER]


def selected_hero(game: Game) -> Entity | None:
    hero = game.entities.get(st.session_state.selected_hero)
    if hero and hero.team == Team.HERO:
        return hero
    return None


def tile_symbol(game: Game, pos: Position, visible_now: set[Position]) -> tuple[str, str, str]:
    if pos not in game.explored_tiles:
        return ("🌫️", "Inexploré", "#0c0f14")

    if pos in visible_now:
        entity = next((e for e in game.entities.values() if e.alive and e.position == pos), None)
        if entity:
            if entity.team == Team.HERO:
                return ("🧙", entity.name, "#26374a")
            return ("👹", entity.name, "#482b2b")

    door = game.quest.board.door_at(pos)
    if door:
        if door.secret and not door.revealed:
            return ("⬛", "Mur", "#111318")
        if door.secret:
            return (("🗝️" if not door.open else "▫️"), "Passage secret", "#3a344a")
        return (("🚪" if not door.open else "▫️"), "Porte ouverte" if door.open else "Porte fermée", "#303846")

    if pos in game.quest.board.walls:
        return ("⬛", "Mur", "#111318")

    chest = game.quest.board.chest_at(pos)
    if chest:
        return (("📦" if not chest.opened else "🗃️"), "Coffre ouvert" if chest.opened else "Coffre", "#3a3428")

    trap = game.quest.board.trap_at(pos)
    if trap and trap.revealed and not trap.disarmed:
        return ("⚠️", "Piège révélé", "#4a3625")
    if trap and trap.disarmed:
        return ("✅", "Piège désarmé", "#263d32")

    zone = game.quest.board.zone_at(pos)
    title = zone.name if zone else "Sol"
    return ("·", title, "#252a33")


def render_board(game: Game) -> None:
    selected = game.entities.get(st.session_state.selected_hero)
    visible_now = game.current_visible_tiles()
    rows: list[str] = []
    for y in range(game.quest.board.height):
        cells: list[str] = []
        for x in range(game.quest.board.width):
            pos = Position(x, y)
            symbol, title, background = tile_symbol(game, pos, visible_now)
            selected_here = selected is not None and selected.alive and selected.position == pos
            border = "3px solid #f6c453" if selected_here else "1px solid #3b4252"
            opacity = "1" if pos in visible_now else ("0.70" if pos in game.explored_tiles else "0.45")
            cells.append(
                f'<td title="{html.escape(title)}" style="width:54px;height:54px;text-align:center;'
                f'font-size:27px;border:{border};background:{background};border-radius:7px;opacity:{opacity}">{symbol}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(
        '<div style="overflow-x:auto"><table style="border-collapse:separate;border-spacing:4px">'
        + "".join(rows)
        + "</table></div>",
        unsafe_allow_html=True,
    )


def log_game_events(events: list[dict]) -> None:
    for event in events:
        if event["type"] == "TrapTriggered":
            actor = st.session_state.game.entity(event["actor_id"])
            log(f"⚠️ {actor.name} déclenche un piège et perd {event['damage']} PV.")
        elif event["type"] == "ZoneDiscovered":
            log(f"🗺️ Nouvelle zone découverte : {event['name']}.")


def perform_move(dx: int, dy: int) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    try:
        destination = Position(hero.position.x + dx, hero.position.y + dy)
        result = game.move(hero.id, destination)
        log(f"{hero.name} se déplace en ({destination.x}, {destination.y}).")
        log_game_events(result["events"])
    except RuleError as exc:
        log(f"Action impossible : {exc}")


def adjacent_enemies(game: Game, actor: Entity) -> list[Entity]:
    visible_now = game.current_visible_tiles()
    return [
        entity
        for entity in game.entities.values()
        if entity.alive
        and entity.team != actor.team
        and entity.position in visible_now
        and actor.position.manhattan(entity.position) == 1
    ]


def adjacent_doors(game: Game, actor: Entity):
    return [
        door
        for door in game.quest.board.doors.values()
        if not door.open and door.visible and actor.position.manhattan(door.position) <= 1
    ]


def adjacent_chests(game: Game, actor: Entity):
    return [
        chest
        for chest in game.quest.board.chests.values()
        if not chest.opened and chest.position in game.explored_tiles and actor.position.manhattan(chest.position) <= 1
    ]


def adjacent_revealed_traps(game: Game, actor: Entity):
    return [
        trap
        for trap in game.quest.board.traps.values()
        if trap.revealed and not trap.disarmed and actor.position.manhattan(trap.position) <= 1
    ]


def attack_target(target_id: str) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    target = game.entity(target_id)
    level_before = hero.level
    try:
        result = game.attack(hero.id, target_id)
        log(
            f"⚔️ {hero.name} attaque {target.name} : {result.hits} touche(s), "
            f"{result.guards} parade(s), {result.damage} dégât(s)."
        )
        if not target.alive:
            log(f"☠️ {target.name} est neutralisé. {hero.name} gagne {target.xp_reward} XP.")
            if hero.level > level_before:
                log(f"✨ {hero.name} atteint le niveau {hero.level} et gagne 1 PV