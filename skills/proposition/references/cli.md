# CLI du skill principal

`MAIN_SKILL_DIR` est le dossier du SKILL principal réellement installé, résolu par sa localisation ; ce n'est pas le répertoire de travail. Toujours passer par l'interpréteur :

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py --help
```

La commande peut aussi être installée par le paquet. Vérifier `--help` sur la version présente avant un appel ; aucune syntaxe `/proposition` n'est garantie par ce document. Les runs vivent hors checkout par défaut. Tous chemins d'artefacts d'un run doivent être relatifs au run.

| Besoin | Sous-commande après le lanceur Python |
|---|---|
| Capacités | `doctor` |
| Distributions upstream | `upstream status` ; `upstream fetch [--family NAME] [--cache DIR]` |
| Run | `init URL [--runs-root DIR] [--profile FILE]` ; `validate RUN_DIR` |
| Collecte | `collect URL --output DIR [--allow-local-fixture] [--max-pages N]` |
| Continuer la couverture | `collect --frontier PREVIOUS_DISCOVERY_JSON --output NEW_DIR [--max-pages N]` — vérifie les preuves précédentes, reprend les destinations restantes dans un lot neuf |
| Source / fait | `source RUN_DIR JSON_FILE` ; `fact RUN_DIR JSON_FILE` |
| Artefact | `artifact RUN_DIR ID FILE --audience public|client|sales|technical|internal [--depends REF...]` |
| Évaluation | `evaluate RUN_DIR REQUIREMENT_ID JSON_FILE` |
| Revue / rapport d'étape | `stage-review RUN_DIR STAGE_ID JSON_FILE` ; `stage-report RUN_DIR STAGE_ID` |
| Projection | `packet RUN_DIR --output DIR --files RELPATH...` |
| Entrée créative | `context-packet RUN_DIR --output DIR --files RELPATH...` — brief public validé, distinct du paquet de livraison final |
| Conservation créative | `freeze-creatives RUN_DIR SELECTION_JSON` ; `check-creatives RUN_DIR` — [contrat et formats](../../proposition-composition/references/preservation.md) |
| Export / inspection | `export SOURCE_HTML OUTPUT_PDF --audience client|sales|technical` ; `inspect PDF --output DIR` |
| Plan / accord | `plan RUN_DIR JSON_FILE` ; `approve RUN_DIR --plan-hash HASH --actor ID --evidence FILE` |
| Publication de test | `publish RUN_DIR --adapter fixture` — explicite, aucun système métier réel |
| Mesure / reçu | `measure RUN_DIR --help` ; `receipt RUN_DIR` |

Pour les JSON, lire le contrat embarqué pertinent dans `scripts/proposition_runtime/contracts/` et le registre dans `scripts/proposition_runtime/data/` ; ne pas inventer des champs compatibles. `validate` vérifie le contrat qu'il annonce, pas la vérité du contenu. Les statuts métier sont `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE` motivé et `STALE` après modification.

L'export imprime une source passive et ses ressources locales ; il n'autorise pas JavaScript ou téléchargements arbitraires. `inspect` ne remplace pas la lecture de toutes les pages. Le faux adaptateur ne peut servir de preuve d'enregistrement dans un système réel. Après effet incertain : recherche et readback avant toute répétition.

`packet` concerne la livraison finale et exige la qualité finale courante. `context-packet` prépare uniquement l'entrée de création à partir du brief public validé et des fichiers explicitement autorisés, avant que les PDF existent. Le stage de publication et ses exigences sont évalués séparément de la qualité documentaire ; l'absence d'accord ne force ni une publication ni une fausse exclusion des obligations.

`layout MANIFEST_JSON` calcule les surfaces à partir de rectangles de placement déclarés (`pages`, `placements` avec `page`, `kind`, `rect`, `source_id`). Sa portée est géométrique : les masques complexes et chevauchements restent bloqués tant que leur surface visible n'est pas établie ; la qualité, les droits et la fidélité ne sont pas déduits du ratio.

La revue d'étape fournit cinq notes explicites, un rôle de réviseur, ses preuves et un reçu d'indépendance lié au même run et au même passage. Les critères/ancres sont dans `data/stages.json` embarqué. `stage-report` calcule l'état à partir des obligations et de cette revue ; il ne génère pas une note à la place du réviseur. Les deux revues globales finales restent requises en plus des treize rapports d'étape.

## Progression et portée

`next-stage RUN_DIR` indique le premier passage applicable non validé. `check-experience RUN_DIR` vérifie la chaîne de preuves créative ; `--stage client.composition` inclut la carte de récit et les pages du PDF. Lire [les champs attendus](experience-evidence.md) avant de créer les artefacts. `inspect --help` expose `--max-pages` pour une limite explicitement demandée ; aucune limite par défaut. Ces contrôles ne produisent pas une note esthétique.
