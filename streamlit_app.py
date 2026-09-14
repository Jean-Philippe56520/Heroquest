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
        st.session_state.log = ["La Crypte des Échos vous attend. Explorez sans savoir ce qui se cache au-delà des murs."]


def reset_game() -> None:
    st.session_state.game = new_game()
    st.session_state.selected_hero = "hero-warden"
    st.session_state.log = ["Nouvelle expédition commencée."]


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
                log(f"✨ {hero.name} atteint le niveau {hero.level} et gagne 1 PV maximum.")
    except RuleError as exc:
        log(f"Attaque impossible : {exc}")


def open_door(door_id: str) -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    try:
        result = game.open_door(hero.id, door_id)
        door = game.quest.board.doors[door_id]
        log(f"{'🗝️' if door.secret else '🚪'} {hero.name} ouvre {'un passage secret' if door.secret else 'une porte'}.")
        log_game_events(result["events"])
    except RuleError as exc:
        log(f"Ouverture impossible : {exc}")


def search_environment() -> None:
    game = st.session_state.game
    hero = selected_hero(game)
    if not hero:
        return
    traps = game.reveal_traps(hero.id)
    secrets = game.search_secret_doors(hero.id)
    if traps:
        log(f"🔎 {hero.name} découvre {len(traps)} piège(s).")
    if secrets:
        log(f"🗝️ {hero.name} découvre {len(secrets)} passage(s) secret(s).")
    if not traps and not secrets:
        log(f"🔎 {hero.name} inspecte les alentours mais ne trouve rien.")


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
        item_names = [str(item.get("name", item.get("id", "objet"))) for item in result.get("items_collected", [])]
        parts: list[str] = []
        if item_names:
            parts.append(", ".join(item_names))
        if result.get("gold_gained"):
            parts.append(f"{result['gold_gained']} pièces")
        log(f"📦 {hero.name} ouvre le coffre et obtient : {', '.join(parts) if parts else 'rien'}.")
    except RuleError as exc:
        log(f"Coffre inaccessible : {exc}")


def equip_item(hero_id: str, item_id: str) -> None:
    game = st.session_state.game
    hero = game.entity(hero_id)
    try:
        game.equip_item(hero_id, item_id)
        log(f"🛡️ {hero.name} équipe {item_id}.")
    except RuleError as exc:
        log(f"Équipement impossible : {exc}")


def monster_turn() -> None:
    game = st.session_state.game
    if game.active_team != Team.HERO:
        return

    game.end_team_turn()
    log("👹 Tour des monstres.")

    for monster in monster_entities(game):
        if not monster.alive or monster.position not in game.explored_tiles:
            continue
        heroes = [hero for hero in hero_entities(game) if hero.alive]
        if not heroes:
            break
        target = min(heroes, key=lambda hero: monster.position.manhattan(hero.position))
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
st.caption("Prototype V0.2 · exploration, brouillard de guerre, secrets, équipement et progression")

with st.sidebar:
    st.header(game.quest.title)
    st.write(game.quest.description)
    st.subheader("Objectifs")
    chest_open, monsters_down, hero_alive = quest_status(game)
    objective_state = [chest_open, monsters_down, hero_alive]
    for done, text in zip(objective_state, game.quest.objectives):
        st.write(("✅ " if done else "⬜ ") + text)

    st.divider()
    st.subheader("Exploration")
    if game.discovered_zone_ids:
        for zone_id in game.discovered_zone_ids:
            zone = game.quest.board.zones.get(zone_id)
            if zone:
                st.write(f"🗺️ {zone.name}")
    else:
        st.caption("Aucune zone découverte")
    st.caption(f"{len(game.explored_tiles)} cases cartographiées")

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
    st.caption("🌫️ inexploré · 🧙 héros · 👹 monstre · 🚪 porte · 🗝️ passage secret · 📦 coffre · ⚠️ piège · ⬛ mur")

    living_heroes = [hero for hero in hero_entities(game) if hero.alive]
    if living_heroes:
        hero_labels = {
            hero.id: f"{hero.name} — niv. {hero.level} — {hero.hp}/{hero.max_hp} PV"
            for hero in living_heroes
        }
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
            if st.button("🔎 Fouiller", use_container_width=True, disabled=game.active_team != Team.HERO):
                search_environment()
                st.rerun()
        with action_cols[1]:
            if doors and st.button("🚪 Ouvrir", use_container_width=True, disabled=game.active_team != Team.HERO):
                open_door(doors[0].id)
                st.rerun()
        with action_cols[2]:
            if chests and st.button("📦 Coffre", use_container_width=True, disabled=game.active_team != Team.HERO):
                open_chest(chests[0].id)
                st.rerun()
        with action_cols[3]:
            if traps and st.button("🛠️ Désarmer", use_container_width=True, disabled=game.active_team != Team.HERO):
                disarm_trap(traps[0].id)
                st.rerun()

        if enemies:
            st.markdown("#### Combat")
            for enemy in enemies:
                if st.button(
                    f"⚔️ Attaquer {enemy.name} ({enemy.hp}/{enemy.max_hp} PV)",
                    key=f"atk-{enemy.id}",
                    disabled=game.active_team != Team.HERO,
                ):
                    attack_target(enemy.id)
                    st.rerun()

        if st.button("⏭️ Terminer le tour des héros", type="primary", use_container_width=True):
            monster_turn()
            st.rerun()
    else:
        st.error("Tous les héros sont hors combat. La quête est perdue.")

with right:
    st.subheader("Équipe")
    for hero in hero_entities(game):
        st.markdown(f"### {hero.name} · niv. {hero.level}")
        st.progress(hero.hp / hero.max_hp if hero.max_hp else 0, text=f"{hero.hp}/{hero.max_hp} PV")
        st.caption(
            f"⚔️ {hero.effective_attack_dice} dés · 🛡️ {hero.effective_defense_dice} dés · "
            f"✨ {hero.xp}/{hero.next_level_xp} XP · 🪙 {hero.gold}"
        )

        if hero.equipment:
            for slot, item in hero.equipment.items():
                st.caption(f"{slot}: {item.get('name', item.get('id', 'Objet'))}")
        else:
            st.caption("Aucun équipement")

        if hero.inventory:
            st.write("**Sac**")
            for item in list(hero.inventory):
                item_name = item.get("name", item.get("id", "Objet"))
                col_item, col_action = st.columns([2, 1])
                col_item.caption(f"• {item_name}")
                if item.get("slot") and col_action.button("Équiper", key=f"equip-{hero.id}-{item.get('id')}"):
                    equip_item(hero.id, str(item.get("id")))
                    st.rerun()
        st.divider()

    st.subheader("Menaces découvertes")
    known_monsters = [monster for monster in monster_entities(game) if monster.position in game.explored_tiles or not monster.alive]
    if known_monsters:
        for monster in known_monsters:
            state = "☠️" if not monster.alive else "👹"
            st.write(f"{state} **{monster.name}** — {monster.hp}/{monster.max_hp} PV")
    else:
        st.caption("Aucune menace identifiée")

    st.divider()
    st.subheader("Journal")
    for message in st.session_state.log[:16]:
        st.write(message)

chest_open, monsters_down, hero_alive = quest_status(game)
if chest_open and monsters_down and hero_alive:
    st.success("🏆 Quête accomplie : le coffre est ouvert, le gardien est vaincu et un héros a survécu.")
elif not hero_alive:
    st.error("💀 Défaite : aucun héros n'a survécu.")
