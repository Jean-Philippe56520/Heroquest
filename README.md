# Code RPG Dungeon Engine

Moteur tactique original pour **Code RPG**, inspire des principes de dungeon-crawler sur plateau : exploration sur grille, portes, pieges, coffres, monstres, combats par des et quetes chargees depuis des fichiers JSON.

> Ce depot n'integre aucun visuel, texte de regle, scenario, nom de personnage ou autre contenu proprietaire de HeroQuest. Le but est de disposer d'un moteur independant, extensible et juridiquement propre.

## Version actuelle : V0.2

La V0.2 ajoute au socle tactique :

- brouillard de guerre persistant ;
- vision locale et zones/salles decouvertes ;
- passages secrets a rechercher puis ouvrir ;
- pieges revelables/desarmables ;
- inventaire porte par le moteur ;
- or et butin ;
- equipement avec bonus d'attaque/defense ;
- XP, niveaux et progression des PV ;
- monstres inactifs tant que leur zone n'a pas ete decouverte ;
- interface Streamlit adaptee a l'exploration ;
- 13 tests unitaires du moteur.

La version publique stable est deployee ici :

**https://heroquest.streamlit.app**

## Demarrage local

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run streamlit_app.py
```

## Architecture

```text
content/                 donnees de quetes et campagnes
src/code_rpg_engine/     moteur de regles pur
reference_sources/       references open source externes, hors build
docs/                    architecture et decisions
scripts/                 outils de maintenance / recuperation des references
streamlit_app.py         interface jouable actuelle
```

Le moteur reste decouple de l'interface. Une application Web, mobile, React ou un serveur multijoueur pourra l'utiliser sans reecrire les regles.

## Deploiement Streamlit Community Cloud

Configuration actuelle :

```text
Repository : Jean-Philippe56520/Heroquest
Branch     : main
Main file  : streamlit_app.py
URL stable : https://heroquest.streamlit.app
```

## Sources open source et inspiration

Deux projets tiers sont conserves comme references techniques :

- `hghero/HeroQuest` — LGPL-2.1, C++/Qt ;
- `g1augusto/HeroQuestCS50Builder` — MIT, Python/Flask ;
- `henriquesimoes/heroquest` — reference d'etude uniquement, aucune licence declaree.

Voir `THIRD_PARTY.md`, `UPSTREAM.lock.json` et `reference_sources/README.md`.

## Prochaines briques recommandees

1. sorts, consommables et effets temporaires ;
2. sauvegarde de campagne ;
3. plusieurs quetes liees en campagne ;
4. editeur de carte ;
5. API FastAPI ;
6. multijoueur temps reel ;
7. couche evenementielle pour narration/LLM.
