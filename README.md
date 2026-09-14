# Code RPG Dungeon Engine

Moteur tactique original pour **Code RPG**, inspire des principes de dungeon-crawler sur plateau : exploration sur grille, portes, pieges, coffres, monstres, combats par des et quetes chargees depuis des fichiers JSON.

> Ce depot n'integre aucun visuel, texte de regle, scenario, nom de personnage ou autre contenu proprietaire de HeroQuest. Le but est de disposer d'un moteur independant, extensible et juridiquement propre.

## Etat du socle

Le prototype `0.1.0` fournit deja :

- grille 2D et cases bloquantes ;
- murs et portes ;
- heros et monstres ;
- deplacement orthogonal avec collision ;
- attaque de melee adjacente ;
- jets de des de combat generiques (`hit`, `guard`, `blank`) ;
- points de vie et mise hors jeu ;
- pieges revelables/desarmables ;
- coffres ouvrables avec butin ;
- chargement d'une quete JSON ;
- gestion simple des tours ;
- tests unitaires sans dependance externe.

## Demarrage

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m code_rpg_engine.demo content/quests/crypt_of_echoes.json
```

## Interface Streamlit V0.1

Une interface jouable solo est disponible dans `streamlit_app.py`. Elle ajoute :

- rendu visuel de la grille ;
- selection du heros actif ;
- deplacement orthogonal ;
- ouverture des portes et coffres ;
- recherche et desarmement des pieges ;
- combat au corps a corps ;
- inventaire de session ;
- journal d'evenements ;
- tour automatique simple des monstres ;
- suivi des objectifs de la quete.

Lancement local :

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Deploiement Streamlit Community Cloud

1. connecter le depot GitHub ;
2. choisir la branche `main` ;
3. choisir `streamlit_app.py` comme fichier d'entree ;
4. deployer.

Le fichier `requirements.txt` installe automatiquement Streamlit.

## Architecture cible

```text
content/                 donnees de quetes et campagnes
src/code_rpg_engine/     moteur de regles pur
reference_sources/       references open source externes, hors build
docs/                    architecture et decisions
scripts/                 outils de maintenance / recuperation des references
```

Le moteur est volontairement decouple de l'interface. Une application Web, Streamlit, React, mobile ou un serveur multijoueur pourra l'utiliser sans reecrire les regles.

## Sources open source et inspiration

Deux projets tiers ont ete identifies comme references techniques :

- `hghero/HeroQuest` — LGPL-2.1, C++/Qt ;
- `g1augusto/HeroQuestCS50Builder` — MIT, Python/Flask ;
- `henriquesimoes/heroquest` — reference d'etude uniquement, aucune licence declaree.

Voir `THIRD_PARTY.md`, `UPSTREAM.lock.json` et `reference_sources/README.md`.

## Prochaines briques recommandees

1. vision / brouillard de guerre ;
2. salles et portes secretes ;
3. inventaire, equipement et sorts ;
4. IA de monstres ;
5. editeur de carte Web ;
6. persistence de campagne ;
7. API serveur et multijoueur ;
8. couche evenementielle pour narration/LLM.
