# Code RPG Dungeon Engine

Moteur tactique original pour **Code RPG**, inspire des principes de dungeon-crawler sur plateau : exploration sur grille, portes, pieges, coffres, monstres, combats par des et quetes chargees depuis des fichiers JSON.

> Ce depot n'integre aucun visuel, texte de regle, scenario, nom de personnage ou autre contenu proprietaire de HeroQuest. Le but est de disposer d'un moteur independant, extensible et juridiquement propre.

## Version actuelle : V0.3

La V0.3 consolide la progression persistante :

- sauvegarde JSON versionnee (`schema_version: 1`) ;
- identifiant unique de sauvegarde et dates de creation/mise a jour ;
- restauration depuis une quete fraiche puis application de l'etat dynamique ;
- positions, PV, XP, niveaux, or, inventaire et equipement des heros ;
- etat des monstres, portes, passages secrets, pieges et coffres ;
- brouillard de guerre et zones decouvertes ;
- round et equipe active ;
- bloc campagne pret pour les futures quetes liees ;
- validation stricte des fichiers avant remplacement de la partie courante ;
- import/export depuis Streamlit ;
- 19 tests automatiques dont un round-trip complet sauvegarde -> chargement.

La version publique stable est deployee ici :

**https://heroquest.streamlit.app**

## Demarrage local

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run streamlit_app.py
```

## Sauvegardes

Dans l'interface Streamlit :

- `Telecharger la sauvegarde` exporte un fichier JSON local ;
- `Charger une sauvegarde` valide le fichier puis restaure la partie ;
- une sauvegarde invalide ou provenant d'une quete inconnue est refusee sans remplacer la partie active.

Le moteur de sauvegarde est dans `src/code_rpg_engine/savegame.py` et ne depend pas de Streamlit.

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

```text
Repository : Jean-Philippe56520/Heroquest
Branch     : main
Main file  : streamlit_app.py
URL stable : https://heroquest.streamlit.app
```

## Sources open source et inspiration

Projets tiers conserves comme references techniques :

- `hghero/HeroQuest` - LGPL-2.1, C++/Qt ;
- `g1augusto/HeroQuestCS50Builder` - MIT, Python/Flask ;
- `henriquesimoes/heroquest` - reference d'etude uniquement, aucune licence declaree.

Voir `THIRD_PARTY.md`, `UPSTREAM.lock.json` et `reference_sources/README.md`.

## Prochaines briques recommandees

1. personnages/classes persistants entre plusieurs quetes ;
2. sorts, consommables et effets temporaires ;
3. campagne multi-quetes ;
4. choix narratifs et evenements persistants ;
5. persistence serveur uniquement lorsque le jeu solo est solide.
