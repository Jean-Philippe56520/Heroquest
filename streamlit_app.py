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

st.set_page_config(page_title="Heroquest", page_icon="⚔️", layout="wide")


def new_game() -> Game:
    return Game(load_quest(QUEST_PATH), rng=random.Random())


def new_save_identity(game: Game) -> dict[str, str]:
    data = build_save(game)
    return {"save_id": data["save_id"], "created_at": data["created_at"]}


def ensure_state() -> None:
    if "game" not in st.session_state:
        st.session_state.game = new_game()
    if "selected_hero" not in st.session_state:
        st.session_state.selected_hero = "hero-warden"
    if "log" not in st.session_state:
        st.session_state.log = ["La Crypte des Échos vous attend."]
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
    restored = restore_game(load_quest(quest_path), data, rng=random.Random())
    hero_list = [e for e in restored.entities.values() if e.team == Team.HERO]
    living = [h for h in hero_list if h.alive]
    if not hero_list:
        raise SaveGameError("la sauvegarde ne contient aucun héros compatible")
    selected = (living or hero_list)[0].id

    # Ne remplacer la session qu'après validation complète.
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


def heroes(game: Game) -> list[Entity]:
    return [e for e in game.entities.values() if e.team == Team.HERO]


def monsters(game: Game) -> list[Entity]:
    return [e for e in game.entities.values() if e.team == Team.MONSTER]


def active_hero(game: Game) -> Entity | None:
    hero = game.entities.get(st.session_state.selected_hero)
    return hero if hero and hero.team == Team.HERO else None


def tile(game: Game, pos: Position, visible: set[Position]) -> tuple[str, str, str]:
    if pos not in game.explored_tiles:
        return "🌫️", "Inexploré", "#0c0f14"
    if pos in visible:
        entity = next((e for e in game.entities.values() if e.alive and e.position == pos), None)
        if entity:
            return ("🧙", entity.name, "#26374a") if entity.team == Team.HERO else ("👹", entity.name, "#482b2b")
    door = game.quest.board.door_at(pos)
    if door:
        if door.secret and not door.revealed:
            return "⬛", "Mur", "#111318"
        if door.secret:
            return ("🗝️" if not door.open else "▫️"), "Passage secret", "#3a344a"
        return ("🚪" if not door.open else "▫️"), ("Porte fermée" if not door.open else "Porte ouverte"), "#303846"
    if pos in game.quest.board.walls:
        return "⬛", "Mur", "#111318"
    chest = game.quest.board.chest_at(pos)
    if chest:
        return ("📦" if not chest.opened else "🗃️"), ("Coffre" if not chest.opened else "Coffre ouvert"), "#3a3428"
    trap = game.quest.board.trap_at(pos)
    if trap and trap.revealed and not trap.disarmed:
        return "⚠️", "Piège révélé", "#4a3625"
    if trap and trap.disarmed:
        return "✅", "Piège désarmé", "#263d32"
    zone = game.quest.board.zone_at(pos)
    return "·", (zone.name if zone else "Sol"), "#252a33"


def render_board(game: Game) -> None:
    selected = game.entities.get(st.session_state.selected_hero)
    visible = game.current_visible_tiles()
    rows: list[str] = []
    for y in range(game.quest.board.height):
        cells: list[str] = []
        for x in range(game.quest.board.width):
            pos = Position(x, y)
            symbol, title, background = tile(game, pos, visible)
            border = "3px solid #f6c453" if selected and selected.alive and selected.position == pos else "1px solid #3b4252"
            opacity = "1" if pos in visible else ("0.70" if pos in game.explored_tiles else "0.45")
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


def handle_events(events: list[dict]) -> None:
    for event in events:
        if event["type"] == "TrapTriggered":
            actor = st.session_state.game.entity(event["actor_id"])
            log(f"⚠️ {actor.name} déclenche un piège et perd {event['damage']} PV.")
        elif event["type"] == "ZoneDiscovered":
            log(f"🗺️ Nouvelle zone découverte : {event['name']}.")


def move_hero(dx: int, dy: int) -> None:
    game = st.session_state.game
    hero = active_hero(game)
    if not hero:
        return
    try:
        destination = Position(hero.position.x + dx, hero.position.y + dy)
        result = game.move(hero.id, destination)
        log(f"{hero.name} se déplace en ({destination.x}, {destination.y}).")
        handle_events(result["events"])
    except RuleError as exc:
        log(f"Action impossible : {exc}")


def adjacent_enemies(game: Game, hero: Entity) -> list[Entity]:
    visible = game.current_visible_tiles()
    return [e for e in game.entities.values() if e.alive and e.team != hero.team and e.position in visible and hero.position.manhattan(e.position) == 1]


def adjacent_doors(game: Game, hero: Entity):
    return [d for d in game.quest.board.doors.values() if not d.open and d.visible and hero.position.manhattan(d.position) <= 1]


def adjacent_chests(game: Game, hero: Entity):
    return [c for c in game.quest.board.chests.values() if not c.opened and c.position in game.explored_tiles and hero.position.manhattan(c.position) <= 1]


def adjacent_traps(game: Game, hero: Entity):
    return [t for t in game.quest.board.traps.values() if t.revealed and not t.disarmed and hero.position.manhattan(t.position) <= 1]


def attack(target_id: str) -> None:
    game = st.session_state.game
    hero = active_hero(game)
    if not hero:
        return
    target = game.entity(target_id)
    level_before = hero.level
    try:
        result = game.attack(hero.id, target_id)
        log(f"⚔️ {hero.name} attaque {target.name} : {result.hits} touche(s), {result.guards} parade(s), {result.damage} dégât(s).")
        if not target.alive:
            log(f"☠️ {target.name} est neutralisé. {hero.name} gagne {target.xp_reward} XP.")
            if hero.level > level_before:
                log(f"✨ {hero.name} atteint le niveau {hero.level} et gagne 1 PV maximum.")
    except RuleError as exc:
        log(f"Attaque impossible : {exc}")


def open_door(door_id: str) -> None:
    game = st.session_state.game
    hero = active_hero(game)
    if not hero:
        return
    try:
        result = game.open_door(hero.id, door_id)
        door = game.quest.board.doors[door_id]
        log(f"{'🗝️' if door.secret else '🚪'} {hero.name} ouvre {'un passage secret' if door.secret else 'une porte'}.")
        handle_events(result["events"])
    except RuleError as exc:
        log(f"Ouverture impossible : {exc}")


def search() -> None:
    game = st.session_state.game
    hero = active_hero(game)
    if not hero:
        return
    found_traps = game.reveal_traps(hero.id)
    secrets = game.search_secret_doors(hero.id)
    if found_traps:
        log(f"🔎 {hero.name} découvre {len(found_traps)} piège(s).")
    if secrets:
        log(f"🗝️ {hero.name} découvre {len(secrets)} passage(s) secret(s).")
    if not found_traps and not secrets:
        log(f"🔎 {hero.name} inspecte les alentours mais ne trouve rien.")


def disarm(trap_id: str) -> None:
    game = st.session_state.game
    hero = active_hero(game)
    if not hero:
        return
    try:
        game.disarm_trap(hero.id, trap_id)
        log(f"🛠️ {hero.name} désarme le piège.")
    except RuleError as exc:
        log(f"Désarmement impossible : {exc}")


def open_chest(chest_id: str) -> None:
    game = st.session_state.game
    hero = active_hero(game)
    if not hero:
        return
    try:
        result = game.open_chest(hero.id, chest_id)
        parts = [str(i.get("name", i.get("id", "objet"))) for i in result.get("items_collected", [])]
        if result.get("gold_gained"):
            parts.append(f"{result['gold_gained']} pièces")
        log(f"📦 {hero.name} ouvre le coffre et obtient : {', '.join(parts) if parts else 'rien'}.")
    except RuleError as exc:
        log(f"Coffre inaccessible : {exc}")


def equip(hero_id: str, item_id: str) -> None:
    game = st.session_state.game
    try:
        game.equip_item(hero_id, item_id)
        log(f"🛡️ {game.entity(hero_id).name} équipe {item_id}.")
    except RuleError as exc:
        log(f"Équipement impossible : {exc}")


def monster_turn() -> None:
    game = st.session_state.game
    if game.active_team != Team.HERO:
        return
    game.end_team_turn()
    log("👹 Tour des monstres.")
    for monster in monsters(game):
        if not monster.alive or monster.position not in game.explored_tiles:
            continue
        living = [h for h in heroes(game) if h.alive]
        if not living:
            break
        target = min(living, key=lambda h: monster.position.manhattan(h.position))
        if monster.position.manhattan(target.position) == 1:
            try:
                result = game.attack(monster.id, target.id)
                log(f"👹 {monster.name} frappe {target.name} et inflige {result.damage} dégât(s).")
                if not target.alive:
                    log(f"☠️ {target.name} tombe au combat.")
            except RuleError as exc:
                log(f"Erreur IA : {exc}")
            continue
        candidates = [p for p in game.quest.board.neighbors(monster.position) if game.quest.board.is_walkable(p, game.entities, mover_id=monster.id)]
        if candidates:
            destination = min(candidates, key=lambda p: p.manhattan(target.position))
            if destination.manhattan(target.position) < monster.position.manhattan(target.position):
                try:
                    game.move(monster.id, destination)
                    log(f"👣 {monster.name} se rapproche de {target.name}.")
                except RuleError as exc:
                    log(f"Erreur IA : {exc}")
    game.end_team_turn()
    log(f"Début du round {game.round_number}.")


def quest_status(game: Game) -> tuple[bool, bool, bool]:
    return (
        all(c.opened for c in game.quest.board.chests.values()),
        all(not m.alive for m in monsters(game)),
        any(h.alive for h in heroes(game)),
    )


ensure_state()
game: Game = st.session_state.game
st.title("⚔️ Heroquest — Dungeon Engine")
st.caption("Prototype V0.3 · sauvegarde JSON, exploration, secrets, équipement et progression")

if "load_notice" in st.session_state:
    st.success(st.session_state.pop("load_notice"))

with st.sidebar:
    st.header(game.quest.title)
    st.write(game.quest.description)
    st.subheader("Objectifs")
    chest_open, monsters_down, hero_alive = quest_status(game)
    for done, text in zip((chest_open, monsters_down, hero_alive), game.quest.objectives):
        st.write(("✅ " if done else "⬜ ") + text)

    st.divider()
    st.subheader("Exploration")
    for zone_id in sorted(game.discovered_zone_ids):
        zone = game.quest.board.zones.get(zone_id)
        if zone:
            st.write(f"🗺️ {zone.name}")
    st.caption(f"{len(game.explored_tiles)} cases cartographiées")
    st.metric("Round", game.round_number)
    st.write(f"Équipe active : **{game.active_team.value}**")

    st.divider()
    st.subheader("Partie")
    identity = st.session_state.save_identity
    save_json = dumps_save(
        game,
        save_id=identity["save_id"],
        created_at=identity["created_at"],
        completed_quests=st.session_state.completed_quests,
    )
    st.download_button(
        "💾 Télécharger la sauvegarde",
        data=save_json,
        file_name=f"heroquest-{game.quest.id}-{identity['save_id'][:8]}.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded = st.file_uploader("📂 Charger une sauvegarde", type=["json"], key="save_upload")
    if uploaded is not None and st.button("Charger cette sauvegarde", use_container_width=True):
        try:
            load_uploaded_save(uploaded.getvalue())
        except SaveGameError as exc:
            st.error(f"Sauvegarde refusée : {exc}")
        else:
            st.session_state.load_notice = "Sauvegarde chargée avec succès."
            st.rerun()
    if st.button("🔄 Recommencer la quête", use_container_width=True):
        reset_game()
        st.rerun()

left, right = st.columns([2.2, 1], gap="large")
with left:
    st.subheader("Plateau")
    render_board(game)
    st.caption("🌫️ inexploré · 🧙 héros · 👹 monstre · 🚪 porte · 🗝️ passage secret · 📦 coffre · ⚠️ piège · ⬛ mur")
    living = [h for h in heroes(game) if h.alive]
    if living:
        labels = {h.id: f"{h.name} — niv. {h.level} — {h.hp}/{h.max_hp} PV" for h in living}
        selected_id = st.radio("Héros actif", list(labels), format_func=lambda hero_id: labels[hero_id], horizontal=True, key="selected_hero")
        hero = game.entity(selected_id)

        st.markdown("#### Déplacement")
        c1, c2, c3 = st.columns(3)
        with c2:
            if st.button("⬆️", use_container_width=True, disabled=game.active_team != Team.HERO):
                move_hero(0, -1)
                st.rerun()
        with c1:
            if st.button("⬅️", use_container_width=True, disabled=game.active_team != Team.HERO):
                move_hero(-1, 0)
                st.rerun()
        with c2:
            if st.button("⬇️", use_container_width=True, disabled=game.active_team != Team.HERO):
                move_hero(0, 1)
                st.rerun()
        with c3:
            if st.button("➡️", use_container_width=True, disabled=game.active_team != Team.HERO):
                move_hero(1, 0)
                st.rerun()

        nearby_enemies = adjacent_enemies(game, hero)
        nearby_doors = adjacent_doors(game, hero)
        nearby_chests = adjacent_chests(game, hero)
        nearby_traps = adjacent_traps(game, hero)
        st.markdown("#### Actions")
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            if st.button("🔎 Fouiller", use_container_width=True, disabled=game.active_team != Team.HERO):
                search()
                st.rerun()
        with a2:
            if nearby_doors and st.button("🚪 Ouvrir", use_container_width=True, disabled=game.active_team != Team.HERO):
                open_door(nearby_doors[0].id)
                st.rerun()
        with a3:
            if nearby_chests and st.button("📦 Coffre", use_container_width=True, disabled=game.active_team != Team.HERO):
                open_chest(nearby_chests[0].id)
                st.rerun()
        with a4:
            if nearby_traps and st.button("🛠️ Désarmer", use_container_width=True, disabled=game.active_team != Team.HERO):
                disarm(nearby_traps[0].id)
                st.rerun()

        for enemy in nearby_enemies:
            if st.button(f"⚔️ Attaquer {enemy.name} ({enemy.hp}/{enemy.max_hp} PV)", key=f"atk-{enemy.id}", disabled=game.active_team != Team.HERO):
                attack(enemy.id)
                st.rerun()
        if st.button("⏭️ Terminer le tour des héros", type="primary", use_container_width=True):
            monster_turn()
            st.rerun()
    else:
        st.error("Tous les héros sont hors combat. La quête est perdue.")

with right:
    st.subheader("Équipe")
    for hero in heroes(game):
        st.markdown(f"### {hero.name} · niv. {hero.level}")
        st.progress(hero.hp / hero.max_hp if hero.max_hp else 0, text=f"{hero.hp}/{hero.max_hp} PV")
        st.caption(f"⚔️ {hero.effective_attack_dice} dés · 🛡️ {hero.effective_defense_dice} dés · ✨ {hero.xp}/{hero.next_level_xp} XP · 🪙 {hero.gold}")
        for slot, item in hero.equipment.items():
            st.caption(f"{slot}: {item.get('name', item.get('id', 'Objet'))}")
        for item in list(hero.inventory):
            item_name = item.get("name", item.get("id", "Objet"))
            col1, col2 = st.columns([2, 1])
            col1.caption(f"• {item_name}")
            if item.get("slot") and col2.button("Équiper", key=f"equip-{hero.id}-{item.get('id')}"):
                equip(hero.id, str(item.get("id")))
                st.rerun()
        st.divider()

    st.subheader("Menaces découvertes")
    known = [m for m in monsters(game) if m.position in game.explored_tiles or not m.alive]
    for monster in known:
        state = "☠️" if not monster.alive else "👹"
        st.write(f"{state} **{monster.name}** — {monster.hp}/{monster.max_hp} PV")
    if not known:
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
