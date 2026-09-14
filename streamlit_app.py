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

QUEST_PATH = ROOT / "content" / "quests" / "crypt_of_echoes.json"

st.set_page_config(page_title="Code RPG - Dungeon Engine", page_icon="⚔️", layout="wide")


def new_game() -> Game:
    quest = load_quest(QUEST_PATH)
    return Game(quest=quest, rng=random.Random())


def ensure_state() -> None:
    if "game" not in st.session_state:
        st.session_state.game = new_game()
    if "selected_hero" not in st.session_state:
        st.session_state.selected_hero = "hero-warden"
    if "log" not in st.session_state:
        st.session_state.log = ["La Crypte des Échos vous attend."]
    if "inventory" not in st.session_state:
        st.session_state.inventory = {}


def reset_game() -> None:
    st.session_state.game = new_game()
    st.session_state.selected_hero = "hero-warden"
    st.session_state.log = ["Nouvelle expédition commencée."]
    st.session_state.inventory = {}


def log(message: str) -> None:
    st.session_state.log.insert(0, message)
    del st.session_state.log[40:]


def tile_symbol(game: Game, pos: Position) -> tuple[str, str]:
    entity = next((e for e in game.entities.values() if e.alive and e.position == pos), None)
    if entity:
        if entity.team == Team.HERO:
            return ("🧙", entity.name)
        return ("👹", entity.name)

    if pos in game.quest.board.walls:
        return ("⬛", "Mur")

    door = game.quest.board.door_at(pos)
    if door:
        return (("🚪" if not door.open else "▫️"), "Porte ouverte" if door.open else "Porte fermée")

    chest = game.quest.board.chest_at(pos)
    if chest:
        return (("📦" if not chest.opened else "🗃️"), "Coffre ouvert" if chest.opened else "Coffre")

    trap = game.quest.board.trap_at(pos)
    if trap and trap.revealed and not trap.disarmed:
        return ("⚠️", "Piège révélé")
    if trap and trap.disarmed:
        return ("✅", "Piège désarmé")

    return ("·", "Sol")


def render_board(game: Game) -> None:
    selected = game.entities.get(st.session_state.selected_hero)
    rows: list[str] = []
    for y in range(game.quest.board.height):
        cells: list[str] = []
        for x in range(game.quest.board.width):
            pos = Position(x, y)
            symbol, title = tile_symbol(game, pos)
            selected_here = selected is not None and selected.alive and selected.position == pos
            border = "3px solid #f6c453" if selected_here else "1px solid #3b4252"
            background = "#2b303b" if pos not in game.quest.board.walls else "#111318"
            cells.append(
                f'<td title="{html.escape(title)}" style="width:52px;height:52px;text-align:center;'
                f'font-size:27px;border:{border};background:{background};border-radius:7px">{symbol}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(
        '<div style="overflow-x:auto"><table style="border-collapse:separate;border-spacing:4px">'
        + "".join(rows)
        + "</table></div>",
        unsafe_allow_html=True,
    )


def hero_entities(game: Game) -> list[Entity]:
    return [e for e in game.entities.values() if e.team == Team.HERO]


def monster_entities(game: Game) -> list[Entity]:
    return [e for e in game.entities.values() if e.team == Team.MONSTER]


def selected_hero(game: Game) -> Entity | None:
    hero = game.entities.get(st.session_state.selected_hero)
    if hero and hero.team == Team.HERO:
        return hero
    return None


def perform_move(dx: int, dy: int) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    try:
        destination = Position(hero.position.x + dx, hero.position.y + dy)
        result = game.move(hero.id, destination)
        log(f"{hero.name} se déplace en ({destination.x}, {destination.y}).")
        for event in result["events"]:
            if event["type"] == "TrapTriggered":
                log(f"⚠️ {hero.name} déclenche un piège et perd {event['damage']} PV.")
    except RuleError as exc:
        log(f"Action impossible : {exc}")


def adjacent_enemies(game: Game, actor: Entity) -> list[Entity]:
    return [
        e
        for e in game.entities.values()
        if e.alive and e.team != actor.team and actor.position.manhattan(e.position) == 1
    ]


def adjacent_doors(game: Game, actor: Entity):
    return [d for d in game.quest.board.doors.values() if not d.open and actor.position.manhattan(d.position) <= 1]


def adjacent_chests(game: Game, actor: Entity):
    return [c for c in game.quest.board.chests.values() if not c.opened and actor.position.manhattan(c.position) <= 1]


def adjacent_revealed_traps(game: Game, actor: Entity):
    return [
        t
        for t in game.quest.board.traps.values()
        if t.revealed and not t.disarmed and actor.position.manhattan(t.position) <= 1
    ]


def attack_target(target_id: str) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    try:
        result = game.attack(hero.id, target_id)
        target = game.entity(target_id)
        log(
            f"⚔️ {hero.name} attaque {target.name} : {result.hits} touche(s), "
            f"{result.guards} parade(s), {result.damage} dégât(s)."
        )
        if not target.alive:
            log(f"☠️ {target.name} est neutralisé.")
    except RuleError as exc:
        log(f"Attaque impossible : {exc}")


def open_door(door_id: str) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    try:
        game.open_door(hero.id, door_id)
        log(f"🚪 {hero.name} ouvre une porte.")
    except RuleError as exc:
        log(f"Ouverture impossible : {exc}")


def search_traps() -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    found = game.reveal_traps(hero.id)
    log(f"🔎 {hero.name} découvre {len(found)} piège(s)." if found else f"🔎 {hero.name} ne détecte aucun piège adjacent.")


def disarm_trap(trap_id: str) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    try:
        game.disarm_trap(hero.id, trap_id)
        log(f"🛠️ {hero.name} désarme le piège.")
    except RuleError as exc:
        log(f"Désarmement impossible : {exc}")


def open_chest(chest_id: str) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    try:
        result = game.open_chest(hero.id, chest_id)
        items = result.get("loot", [])
        st.session_state.inventory.setdefault(hero.id, []).extend(items)
        names = ", ".join(str(item.get("name", item.get("id", "objet"))) for item in items) or "rien"
        log(f"📦 {hero.name} ouvre le coffre et obtient : {names}.")
    except RuleError as exc:
        log(f"Coffre inaccessible : {exc}")


def monster_turn() -> None:
    game = st.session_state.game
    if game.active_team != Team.HERO:
        return

    game.end_team_turn()
    log("👹 Tour des monstres.")

    for monster in monster_entities(game):
        if not monster.alive:
            continue
        heroes = [h for h in hero_entities(game) if h.alive]
        if not heroes:
            break
        target = min(heroes, key=lambda h: monster.position.manhattan(h.position))
        if monster.position.manhattan(target.position) == 1:
            try:
                result = game.attack(monster.id, target.id)
                log(f"👹 {monster.name} frappe {target.name} et inflige {result.damage} dégât(s).")
                if not target.alive:
                    log(f"☠️ {target.name} tombe au combat.")
            except RuleError as exc:
                log(f"Erreur IA : {exc}")
            continue

        candidates = [
            pos
            for pos in game.quest.board.neighbors(monster.position)
            if game.quest.board.is_walkable(pos, game.entities, mover_id=monster.id)
        ]
        if candidates:
            destination = min(candidates, key=lambda pos: pos.manhattan(target.position))
            if destination.manhattan(target.position) < monster.position.manhattan(target.position):
                try:
                    game.move(monster.id, destination)
                    log(f"👣 {monster.name} se rapproche de {target.name}.")
                except RuleError as exc:
                    log(f"Erreur IA : {exc}")

    game.end_team_turn()
    log(f"Début du round {game.round_number}.")


def quest_status(game: Game) -> tuple[bool, bool, bool]:
    chest_open = all(chest.opened for chest in game.quest.board.chests.values())
    monsters_down = all(not monster.alive for monster in monster_entities(game))
    hero_alive = any(hero.alive for hero in hero_entities(game))
    return chest_open, monsters_down, hero_alive


ensure_state()
game: Game = st.session_state.game

st.title("⚔️ Code RPG — Dungeon Engine")
st.caption("Prototype V0.1 Streamlit · moteur tactique original · aucun asset HeroQuest propriétaire")

with st.sidebar:
    st.header(game.quest.title)
    st.write(game.quest.description)
    st.subheader("Objectifs")
    chest_open, monsters_down, hero_alive = quest_status(game)
    objective_state = [chest_open, monsters_down, hero_alive]
    for done, text in zip(objective_state, game.quest.objectives):
        st.write(("✅ " if done else "⬜ ") + text)

    st.divider()
    st.metric("Round", game.round_number)
    st.write(f"Équipe active : **{game.active_team.value}**")
    if st.button("🔄 Recommencer la quête", use_container_width=True):
        reset_game()
        st.rerun()

left, right = st.columns([2.2, 1], gap="large")

with left:
    st.subheader("Plateau")
    render_board(game)
    st.caption("🧙 héros · 👹 monstre · 🚪 porte · 📦 coffre · ⚠️ piège révélé · ⬛ mur")

    living_heroes = [hero for hero in hero_entities(game) if hero.alive]
    if living_heroes:
        hero_labels = {hero.id: f"{hero.name} — {hero.hp}/{hero.max_hp} PV" for hero in living_heroes}
        selected_id = st.radio(
            "Héros actif",
            options=list(hero_labels),
            format_func=lambda hero_id: hero_labels[hero_id],
            horizontal=True,
            key="selected_hero",
        )
        hero = game.entity(selected_id)

        st.markdown("#### Déplacement")
        c1, c2, c3 = st.columns(3)
        with c2:
            if st.button("⬆️", key="up", use_container_width=True, disabled=game.active_team != Team.HERO):
                perform_move(0, -1)
                st.rerun()
        with c1:
            if st.button("⬅️", key="left", use_container_width=True, disabled=game.active_team != Team.HERO):
                perform_move(-1, 0)
                st.rerun()
        with c2:
            if st.button("⬇️", key="down", use_container_width=True, disabled=game.active_team != Team.HERO):
                perform_move(0, 1)
                st.rerun()
        with c3:
            if st.button("➡️", key="right", use_container_width=True, disabled=game.active_team != Team.HERO):
                perform_move(1, 0)
                st.rerun()

        st.markdown("#### Actions")
        enemies = adjacent_enemies(game, hero)
        doors = adjacent_doors(game, hero)
        chests = adjacent_chests(game, hero)
        traps = adjacent_revealed_traps(game, hero)

        action_cols = st.columns(4)
        with action_cols[0]:
            if st.button("🔎 Chercher pièges", use_container_width=True, disabled=game.active_team != Team.HERO):
                search_traps()
                st.rerun()
        with action_cols[1]:
            if doors:
                if st.button("🚪 Ouvrir porte", use_container_width=True, disabled=game.active_team != Team.HERO):
                    open_door(doors[0].id)
                    st.rerun()
        with action_cols[2]:
            if chests:
                if st.button("📦 Ouvrir coffre", use_container_width=True, disabled=game.active_team != Team.HERO):
                    open_chest(chests[0].id)
                    st.rerun()
        with action_cols[3]:
            if traps:
                if st.button("🛠️ Désarmer", use_container_width=True, disabled=game.active_team != Team.HERO):
                    disarm_trap(traps[0].id)
                    st.rerun()

        if enemies:
            st.markdown("#### Combat")
            for enemy in enemies:
                if st.button(f"⚔️ Attaquer {enemy.name} ({enemy.hp}/{enemy.max_hp} PV)", key=f"atk-{enemy.id}"):
                    attack_target(enemy.id)
                    st.rerun()

        if st.button("⏭️ Terminer le tour des héros", type="primary", use_container_width=True):
            monster_turn()
            st.rerun()
    else:
        st.error("Tous les héros sont hors combat. La quête est perdue.")

with right:
    st.subheader("État de l'équipe")
    for hero in hero_entities(game):
        st.write(f"**{hero.name}**")
        st.progress(hero.hp / hero.max_hp if hero.max_hp else 0, text=f"{hero.hp}/{hero.max_hp} PV")
        items = st.session_state.inventory.get(hero.id, [])
        if items:
            for item in items:
                st.caption(f"• {item.get('name', item.get('id', 'Objet'))}")
        else:
            st.caption("Inventaire vide")

    st.divider()
    st.subheader("Monstres")
    for monster in monster_entities(game):
        state = "☠️" if not monster.alive else "👹"
        st.write(f"{state} **{monster.name}** — {monster.hp}/{monster.max_hp} PV")

    st.divider()
    st.subheader("Journal")
    for message in st.session_state.log[:14]:
        st.write(message)

chest_open, monsters_down, hero_alive = quest_status(game)
if chest_open and monsters_down and hero_alive:
    st.success("🏆 Quête accomplie : le coffre est ouvert, le gardien est vaincu et un héros a survécu.")
elif not hero_alive:
    st.error("💀 Défaite : aucun héros n'a survécu.")
