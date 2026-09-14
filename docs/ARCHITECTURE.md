# Architecture

## Principe

Le moteur est **headless** : aucune UI, aucun stockage externe et aucune dependance reseau dans le coeur. Toutes les actions passent par un etat de jeu deterministe et des regles testables.

## Modules

- `models.py` : entites et objets de domaine.
- `board.py` : topologie de grille, collisions, portes, pieges et coffres.
- `dice.py` : des de combat generiques avec RNG injectable.
- `combat.py` : resolution d'une attaque.
- `content.py` : chargement et validation d'une quete JSON.
- `game.py` : orchestration des tours et commandes haut niveau.
- `demo.py` : demonstration console minimale.

## Evolution vers monde persistant

La couche suivante devra introduire un journal d'evenements :

```text
Command -> Rules Engine -> Domain Events -> State Store
                         -> Narrative/LLM
                         -> WebSocket clients
```

Exemples d'evenements : `ActorMoved`, `DoorOpened`, `TrapTriggered`, `EntityDamaged`, `MonsterDefeated`, `ChestOpened`, `QuestFlagSet`.

Le LLM ne doit pas modifier l'etat directement. Il propose des intentions ou enrichit la narration ; le moteur valide les regles et produit les evenements autorises.
