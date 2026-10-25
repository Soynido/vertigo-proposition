# Validation production : URL du repo + URL du site

Lire lors de l'ajout, du gel, de l'intégration ou de la modification d'une capacité, d'un contrat, d'un skill, d'une procédure ou d'un contrôle affectant le résultat de `proposition`. L'intégration technique précède cette qualification ; elle ne vaut pas acceptation autonome ni disponibilité prouvée pour les collaborateurs.

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
