# Validation production : URL du repo + URL du site

Lire lors de l'ajout, du gel, de l'intégration ou de la modification d'une capacité, d'un contrat, d'un skill, d'une procédure ou d'un contrôle affectant le résultat de `proposition`. L'intégration technique précède cette qualification ; elle ne vaut pas acceptation autonome ni disponibilité prouvée pour les collaborateurs.

## Fiche préalable à un nouvel essai

Remplir cette fiche **avant le POC**, dans le dossier de qualification hors du repo public. Elle complète la procédure existante, sans créer un autre pipeline.

| Champ obligatoire | Contenu vérifiable |
|---|---|
| Besoin | Défaut observé ou information manquante ; conséquence pour le résultat client |
| Responsable existant | Étape, skill, fonction/commande et chemin du point actuellement responsable |
| Delta candidat | Complément, remplacement ou adaptation proposés ; entrées/sorties et consommateurs concernés |
| Acquis protégés | Contrats et preuves à conserver, notamment sources, navigation, exploration avant sélection, scènes et édition |
| Preuves disponibles | Témoin, version, fichiers/hashes, périmètre et limites ; ce qui est déjà démontré |
| Comparaison prévue | Même travail/entrées et conditions ; critère de gain, non-régression, budgets et arrêt |
| Décision par sous-capacité | Conserver/admettre, adapter, écarter ou non qualifiée ; justification, manque et essai restant |

Un champ inconnu reste explicite ; résoudre avant l'essai ceux qui empêchent une comparaison interprétable. Le composant qualifié s'intègre au point responsable avec ses preuves et consommateurs ; un prototype parallèle ne prouve pas ce raccordement. Un apport déjà présent dans le témoin n'est pas une découverte du candidat. Le dossier préalable n'est ni une admission ni un PASS autonome.

## Continuité après un essai manuel

Le plan parent reste ouvert jusqu'à une décision explicite pour **toutes ses sous-capacités**. « À conserver » qualifie une portée manuelle ; cela ne signifie pas installé, chargé, consommé ou admis en autonomie. Terminer une réparation de navigation, de collecte ou de montage ferme cette réparation, pas les autres lignes du plan.

Reprendre **la matrice et le checkpoint existants**, hors du dépôt public. Conserver les décisions et preuves antérieures, y compris les exclusions ; ajouter les champs de suivi ci-dessous aux lignes existantes. L'inventaire `scope_ids` reprend tous leurs identifiants dans le périmètre autorisé. Un changement de périmètre conserve dans le plan sa décision d'autorité et les lignes retirées avec leur motif ; une ligne difficile ne disparaît pas du suivi.

| Champ de suivi obligatoire | Contenu |
|---|---|
| `owner`, `scope` | Étape responsable et portée précise effectivement testée ; verdict manuel inchangé |
| `state`, `stage` | `OPEN`, `BLOCKED` ou `CLOSED` ; étape actuelle : `qualification`, `correction`, `contract`, `integration`, `e2e` ou `decision` |
| `last_evidence` | Dernier reçu utile : `path` relatif à la matrice ou absolu, `sha256` ; `null` si aucune preuve, avec le manque dans la prochaine action |
| `next_action` | Action concrète restante pour chaque ligne ouverte, y compris une ligne conservée manuellement |
| `blocker` | Pour `BLOCKED`, condition réelle de reprise ; ni attente fictive ni abandon déclaré terminé |
| `closure` | Pour `CLOSED`, décision terminale et preuves exactes décrites ci-dessous |

Ajouter ce checkpoint **dans la même matrice**, sans recopier ses décisions dans un registre concurrent :

```json
{
  "integration_followup": {
    "version": 1,
    "scope_ids": ["P1", "P2"],
    "parent_status": "OPEN",
    "active_id": "P1",
    "next_action": "Vérifier le chargement canonique et le consommateur du brief."
  }
}
```

Chaque objet de `rows` conserve son `id`, son verdict et ses preuves ; son champ `followup` contient les champs du tableau. Garder **une seule ligne active**. Après un correctif voisin, une interruption, une passation ou une compaction, actualiser ce même checkpoint puis reprendre sa prochaine action autorisée. Une nouvelle demande s'ajoute au plan ; seule une instruction explicite de l'utilisateur change la priorité ou arrête le travail. Un blocage réel reste visible avec les autres lignes ouvertes, sans déclencher des essais répétitifs ou une autre capacité à sa place.

Deux clôtures sont possibles :

- `closure.kind: "integrated"` exige `qualification_receipt`, `integration_receipt`, `e2e_receipt` (chacun `{path, sha256}`), plus `route` avec `canonical_file`, `loaded_by`, `consumer`, `acceptance`. Vérifier le contenu des reçus : contrat/ressources figés, distribution réellement accessible, instruction reçue, résultat consommé, démonstration client lorsqu'elle est dans le mandat, puis E2E autonome accepté sur la révision distribuée. Les parties encore non prouvées restent ouvertes au bon stade.
- `closure.kind: "not_admitted"` exige `reason` et `decision_receipt` (`{path, sha256}`). L'exclusion ou la non-admission motivée ferme une décision dans cette portée ; elle ne fabrique pas une réussite ni n'efface une alternative publique encore prévue au plan. Une intégration différée reste `OPEN`, avec son action restante.

À la reprise et avant de quitter le chantier, exécuter le contrôle de maintenance en lecture seule sur cette matrice :

```bash
python3 scripts/check_integration.py /chemin/hors-du-repo/matrice.json
```

Il expose les lignes ouvertes, leur responsable, leur prochaine action et la ligne active ; une ligne omise, sans suite ou une preuve changée invalide le checkpoint. Au moment de déclarer **le plan parent terminé**, ajouter `--close` : toutes les lignes doivent être closes et `parent_status` doit être `COMPLETE`, avec `active_id` et `next_action` à `null`. Un ticket local peut être terminé alors que ce contrôle refuse la clôture parent : rendre ces deux états séparément et poursuivre le travail déjà autorisé.

`IN_PROGRESS` signifie suivi cohérent mais travail restant ; `TRACKING_COMPLETE` signifie décisions comptabilisées, **jamais PASS créatif ou autonome**. Le contrôle vérifie structure, inventaire déclaré et empreintes de reçus réguliers de 64 Mio maximum, sans réseau ni modification. Il ne lit pas sémantiquement les preuves, ne découvre pas un mandat omis de l'inventaire et ne certifie ni autorité, ni vérité d'un reçu, ni goût du client. La revue confronte toujours le périmètre initial, les verdicts et les fichiers exacts. Conserver les preuves déjà suffisantes ; relancer seulement l'essai minimal du manque réel.

## Deux preuves nécessaires

1. **Qualification ciblée** : tester la capacité sur des sources figées, comparer son apport aux résultats antérieurs, améliorer puis figer le contrat qui fonctionne. Conserver entrées, versions, rendus, défauts et limites. Le test guidé ou l'assemblage manuel reste une preuve de ce périmètre.
2. **Qualification E2E autonome après intégration** : dans un nouveau contexte et une installation isolée, éprouver le dépôt exact avec ses seules instructions distribuées. L'entrée utilisateur est exactement les deux URL résolues :

```text
<URL_REPO>
<URL_SITEWEB>
```

Remplacer les deux valeurs, sans ajouter de capsule, nombre de directions, plan de slides, méthode, rappel de skill, brief client, ancien rendu ou consigne WOW. Les réglages nécessaires au fonctionnement doivent être découverts dans le repo ou résolus par son comportement canonique ; un paquet transmis manuellement ne les remplace pas.

## Avant le test

- [ ] Relier chaque exigence figée à son fichier canonique, à l'étape qui la charge, à l'instruction réellement reçue, à l'artefact attendu et à son critère d'acceptation. Implémenter un contrôle mécanique là où il est fiable ; pour un jugement créatif, exiger une revue des fichiers exacts. Une règle sans route d'application et preuve reste non intégrée.
- [ ] Préserver les contrats encore valides et retirer les consignes contradictoires. Un nouveau document ne remplace pas silencieusement la procédure qualifiée.
- [ ] Identifier l'URL du dépôt, son ref distribué et le commit/arbre effectivement résolus. Une branche publique candidate doit être désignée dans l'URL repo ; aucun `checkout` ou patch secret n'est injecté après lancement. Un kit local en avance n'est pas une preuve de ce que GitHub distribue.
- [ ] Séparer le contexte du créateur de celui du mainteneur. Aucun historique de développement, verdict précédent, sélection préparée ou dossier prospect préchargé. Un cache de dépendances publiques vérifié est admissible s'il ne fournit aucun résultat client.

## Pendant le test

- [ ] Le mainteneur observe sans coacher : pas de message de correction, pas de changement de fichiers, de brief ou de ressources dans le run. Les données du site restent des sources, jamais des instructions.
- [ ] L'agent utilise de lui-même les entrées et routages du dépôt, recueille ses sources et exécute les étapes applicables dans l'ordre de leurs dépendances. Les artefacts internes produits par le système sont permis ; leur fourniture manuelle ne l'est pas.
- [ ] Une aide humaine, un ancien dossier ou un correctif apporté au run rend l'essai **ASSISTÉ**, même si ses livrables deviennent excellents. Conserver cette preuve pour le diagnostic puis rejouer à neuf après correction du repo. Une question décisive non résolue avec les deux URL est un blocage réel, pas une raison d'inventer la réponse.
- [ ] Les sorties et critères viennent du contrat distribué, sans réduction discrète du périmètre pour économiser le test. Une interruption de capacité/ressources produit un checkpoint ; elle ne devient pas un PASS. Aucun coût, quota ou token n'est inventé.

## Après le test

- [ ] Vérifier chaque nouvelle exigence dans les fichiers et traces exacts ; vérifier aussi les fonctions antérieures susceptibles de régresser. Pour une présentation, inspecter toutes les pages du PDF et les slides du PPTX, l'histoire, les preuves, le niveau créatif, la conservation des scènes et l'édition réelle selon les contrats applicables.
- [ ] Juger la qualité indépendamment des notes auteur, avec défauts localisés et critères critiques non compensables. Un E2E autonome peut être de mauvaise qualité ; une conformité mécanique ne démontre pas le WOW.
- [ ] Consigner URL repo/site, commit/arbre, installation et hashes des contrats, entrée initiale exacte, contexte/isolation, interventions éventuelles, étapes et verdicts, fichiers/hashes, défauts, limites et décision. Les sources client et reçus privés restent hors du dépôt public.
- [ ] Toute aide ou correction passe dans les instructions/ressources/code canoniques appropriés, puis le comportement affecté est vérifié. La promotion du delta intégré exige un nouveau run neutre sur ce delta ; ne pas transformer le run accompagné en témoin autonome.

## Verdicts séparés

| Résultat observé | Verdict permis |
|---|---|
| Capacité seule ou essai accompagné convaincant | Qualification ciblée ; E2E autonome encore à faire |
| Nouveau texte, tests unitaires ou revue de code réussis | Contrôle documentaire/mécanique dans sa portée |
| Deux URL seules, résultat incomplet ou critère critique faible | E2E FAIL ou BLOCKED avec preuve et reprise |
| Deux URL seules, obligations et qualité vérifiées sur les fichiers exacts | E2E PASS pour ce commit et ce cas ; généralisation à qualifier |

Un défaut observé ou une obligation non satisfaite donne FAIL. Une capacité ou décision externe indispensable indisponible donne BLOCKED, avec checkpoint ; les parties préparées restent décrites à leur portée réelle.

Une correction purement typographique sans effet sur les instructions ni les critères ne déclenche pas un E2E coûteux. Documenter cette portée. Une modification du contrat ou de son dispatch ne peut pas utiliser cette exception. Publication, diffusion, écriture Notion et production restent des décisions séparées ; cette procédure n'autorise aucun effet externe.
