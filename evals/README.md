# Cas comportementaux publics

- `cases/public-company.json` : une entreprise fictive et des preuves limitées.
- `cases/behavior-cases.json` : neuf tâches, défauts recherchés et critères sémantiques.
- `results/baseline-summary.json` : jugement critère par critère du baseline réellement observé, sans prétendre que les skills étaient chargés.
- `results/guided-summary.json` : jugement du contrôle guidé ; 39 critères satisfaits, 4 partiels, aucun échec sur cet essai textuel. Les deux réponses intégrales fictives sont conservées dans `results/*-response.md`.
- `cases/untrusted-evidence.json` et `results/untrusted-summary.json` : un autre contexte frais a reçu quatre tentatives d'instruction dans des sources fictives. Elles ont été exclues sans action externe. Un essai textuel ne certifie pas une sandbox ni un parseur PDF.

Pour un essai aveugle, transmettre uniquement le paquet et les champs `id`/`task`. Ne pas transmettre `observe`, `failure_to_probe`, résultats ni corrections au testeur. Baseline sans guidance ; variante guidée avec SKILL et références pertinentes. Même tâche, paquet et contraintes ; un contexte frais par échantillon. Ne pas lancer de vrai connecteur, envoi ou écriture métier.

Le juge vérifie les choix et livrables, pas la présence de mots. `PASS` signifie critère satisfait dans la réponse, `PARTIAL` signifie réponse utile mais preuve ou partie manquante, `FAIL` signifie comportement contraire/omission décisive. `NOT_RUN` n'est pas un échec comportemental. Les cas textuels ne prouvent pas l'utilisation du navigateur, la qualité graphique ou l'export réel d'un PDF.

Les barèmes d'évaluation métier restent candidats sans calibration humaine. Voir `docs/qualification.md` pour le protocole et ses limites.

## Contrat créatif

`cases/creative-contract.json` décrit six situations : mondes réellement distincts en PDF, prolongement d'une direction déjà choisie, précision « immersif » sous pression de remise, analyse avant création, livraison éditable avec contexte compilé et dispatch explicite du contrat. Transmettre seulement `id`/`task` au créatif avec son paquet public ; les champs `observe` et `judge` servent à la revue indépendante. Le [contrat](../skills/proposition-creative/references/creative-contract.md) est la guidance de la variante guidée, pas un résultat de test.

Conserver rendus, chronologie scène→inspection→comparaison→composition, fichiers exacts et observations hors checkout pour les clients réels. Les secteurs doivent varier sans recycler une identité. Une génération réussie ne garantit ni un effet WOW reproductible, ni une hausse de performance ; la conformité au protocole et la qualité esthétique sont deux jugements distincts.
