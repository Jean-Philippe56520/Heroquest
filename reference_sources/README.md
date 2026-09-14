# Reference sources

Ce dossier reste hors du build et n'est pas versionne avec les sources tierces elles-memes.

Pour recuperer localement les deux references licenciees, executer :

```bash
bash scripts/fetch_reference_sources.sh
```

Le script clone puis positionne chaque depot sur le commit epingle dans `UPSTREAM.lock.json`.

Le depot `henriquesimoes/heroquest`, sans licence declaree, n'est volontairement pas clone par le script.
