---
name: proposition-technical
description: Use when a stabilized proposal needs an implementation handoff, especially when stack, booking, content sources or actual build readiness remain uncertain.
license: MIT
---

# Transmettre le projet à réaliser

Recevoir le projet final, sa source éditable, ses décisions et les sources techniques encore valides. Lire [le contrat de reprise](references/handoff.md). Dériver la transmission de cette révision ; ne pas relancer toute la recherche sans manque nommé.

Le paquet reçu contient les empreintes courantes de la source client, carte, catalogue et PDF/PPTX. Relier chaque partie à ses pages/zones et à la mission effectivement proposée. Enregistrer `technical-handoff`, puis `technical-source`/`technical-pdf`, avec les dépendances client ; une nouvelle révision périme les dérivés concernés. Le manifeste final inventorie les pièces sans devenir leur entrée, pour éviter un cycle de dépendances.

Décrire parcours et routes, contenus, composants, interactions, états desktop/mobile, actifs, droits et dépendances. Pour CMS, hébergement, agence actuelle, booking ou intégration : distinguer déclaré, observé, hypothèse et inconnu, avec source précise et limite. Une mention de pilote ou un indice visuel ne confirme pas un fournisseur en production.

Associer à chaque partie une décision de conception, un comportement attendu, ses entrées/sorties, dépendances, risques et critère d'acceptation. Conserver les questions qui empêchent de réaliser ou vérifier. Une maquette ne prouve pas une implémentation ; un PDF ne prouve pas un parcours fonctionnel.

## Sortie

Dossier de reprise : périmètre de la mission, carte parcours/composants, sources et médias, matrice des certitudes, dépendances et accès à obtenir, critères d'acceptation, étapes de réalisation et contrôles. Chaque fait technique pointe vers la source ou la vérification nécessaire. L'identité d'un responsable reste un rôle tant qu'elle n'est pas confirmée.

Le dossier propose la prochaine action utile sans lancer automatiquement codage, intégration, formulaire réel ou déploiement.

## Exécution et reprise

Produire depuis la proposition client stabilisée selon [les dépendances de passation](../proposition/references/performance.md). Conserver les limites et actifs réellement validés ; ne pas reconstruire le résultat client pour satisfaire une tâche interne et ne pas publier depuis un worker.
