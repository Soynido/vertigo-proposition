---
name: proposition
description: Use when a company URL is provided for an agency proposal, a client presentation, or continuation of a proposal with client, sales and technical deliverables.
license: MIT
---

# Proposition

Construire une proposition d'agence propre à l'entreprise, depuis son URL. L'URL suffit pour commencer : rechercher les éléments accessibles, distinguer faits et hypothèses, produire le brief. Demander uniquement une décision réellement nécessaire, jamais un questionnaire de démarrage systématique.

## Format et première commande

Après installation, deux URL seules déclenchent le parcours **web** : proposition commerciale interactive, sources éditables et lien public Vercel vérifié. Retrouver le profil et le launcher dans `.vertigo/setup.json`, puis initialiser immédiatement :

```bash
python3 MAIN_SKILL_DIR/scripts/proposition.py init URL_SITE --profile WORKSPACE/.vertigo/profile.json --delivery-format web
```

Résoudre ces chemins depuis l'installation réelle. Une demande documentaire explicite choisit `--delivery-format documents`. Le format est immuable ; un run historique sans champ de format reste documentaire. Lire [le contrat web](references/web-delivery.md) pour le web ; les obligations PDF/PPTX et dossiers internes ci-dessous concernent seulement `documents`. Le web est un parcours complet de ce format, sans exception de mandat créatif inventée.

Objectif600secondes jusqu'au lien vérifié/remis ; plafond de qualification1200secondes, checkpoint conservé. Deux tâches indépendantes simultanées au maximum, un prospect en qualification à la fois. Ne pas réduire les méthodes, l'exploration ou les revues pour passer le délai. Le chronomètre `web budget` commence à `init` ; la durée complète depuis la demande exige aussi les horodatages hôte, sinon cette partie reste inconnue.

Au collaborateur, parler simplement et brièvement : expliquer le travail utile et la décision suivante, comme à une personne non technique. Donner une nouvelle seulement lorsqu'elle apporte une information utile ; garder les IDs, outils et mécanismes internes dans les preuves. Pendant cette commande, ajouter le relevé bref temps/tokens/ressources décrit dans [les capacités](references/capabilities.md), avec « non disponibles » pour les compteurs réellement inaccessibles.

## Reprendre et travailler

1. Résoudre le dossier installé de ce SKILL comme `MAIN_SKILL_DIR`. Lire [le routage](references/workflow.md) et la dernière preuve du run. Utiliser `next-stage RUN_DIR` pour reprendre le premier passage incomplet ou périmé ; conserver les résultats encore valides. Les notes dans un fichier isolé ne remplacent pas les preuves enregistrées.
2. Exécuter le doctor de ce format puis, en web, `web preflight RUN_DIR` avant la collecte (accès/projet actuels, aucune écriture fournisseur). Lire [les reçus de capacités](references/capabilities.md). Les quatre familles attendues sont SEO/GEO, Impeccable, Apple Design et Scroll Craft ; une famille absente reste indisponible. Adapter une méthode utile sans prétendre avoir exécuté ses outils.
3. Produire des sorties contrôlables, dans l'ordre de leurs dépendances : couverture du site et des canaux, modèle sourcé, analyses, réconciliation, **brief public explicite**, direction, **histoire et mission de l'agence explicites** selon [le contrat de montage](../proposition-story/references/argument.md), composition et revues. En web, plan d'expérience préalable, HTML/moteur et publication vérifiée ; en documents, dossiers internes, exports et contrôles documentaires. Employer un spécialiste seulement sur son besoin ; les références de ce skill permettent aussi la voie autonome.
   Avant la création, transmettre le brief issu des sources analysées, avec observations, changements recommandés, objectifs et codes de marque à préserver, selon [la passation stratégique](../proposition-strategy/references/brief.md). Pour tout nouveau prospect, suivre [le lancement créatif](../proposition-creative/SKILL.md#lancement) : lecture du contrat installé et reprise de sa capsule dans le dispatch. Explorer au moins deux mondes, rendre et comparer leurs scènes centrales, puis sélectionner avant les déclinaisons complètes. Le besoin commercial peut être le même ; le brief ne choisit pas sa réponse visuelle à la place du créatif. Une instruction externe explicite peut imposer une direction ou un nombre, avec preuve selon le contrat. Garder le format demandé ; une exploration seule ne devient pas un parcours complet validé.
4. Transmettre à la création uniquement une projection publique minimale, avec liste de fichiers et empreintes. Créatifs et réviseurs travaillent dans de nouveaux contextes sans historique privé. L'absence de cette capacité bloque le gate indépendant, pas la préparation locale autorisée.
   Au montage, charger K01–K08. En web, continuer dans le même contexte créatif, enregistrer `web plan` avant la homepage, puis développer, construire et inspecter le build exact. En documents, appliquer [le préalable de composition](references/experience-evidence.md#plan-de-composition-préalable) avant la fabrication complète. La voie publique peut démontrer l'approche avec les propres scènes retenues, sans bibliothèque privée indispensable. Exploration et intentions gelées restent requises.
5. En web, obtenir les deux revues indépendantes, puis `web publish` et `web verify` avec la politique privée déjà configurée ; remettre le lien exact, sources/crédits et limites. Ne pas fabriquer un accord humain, créer un projet ou modifier un domaine pendant le run. En documents, livrer les trois PDF séparés et leurs sources, `Proposition.pptx` éditable et `Contexte client.md` selon [le contrat documentaire](references/editable-delivery.md). Vérifier les vrais fichiers ; une note ou un export partiel ne suffit pas.

Une demande limitée à une exploration conserve sa portée, sans prétendre livrer le parcours complet. En documents, `parameters.delivery_scope: client` exclut les dossiers internes et `full` les conserve. En web, la portée de livraison est client et le profil de format remplace les preuves documentaires correspondantes ; les sources, méthodes et fonctions commerciales communes restent requises.

## Preuve de passage

Chaque passation indique : étape, état, entrées et empreintes, décisions et sources, sorties et empreintes, obligations non prouvées, capacités réellement employées, prochain travail. Noter chaque étape selon [ses cinq critères](references/stage-quality.md) et contrôler chacune des [81 obligations](references/acceptance.md). Séparer complétude, qualité, droit de diffusion et publication. Une nouvelle source invalide les jugements et exports dépendants.

Utiliser [la CLI](references/cli.md) pour persister l'état ; ses reçus ne remplacent pas le jugement métier. Lire [le contrat commercial](references/proposal.md) avant brief/histoire/Sales. La présence de fichiers, un score isolé ou une urgence ne constituent pas une preuve finale.

## Exécution et reprise

Lire [les règles de reprise et d'exécution native](references/performance.md) dès la coordination : réserver les tâches prêtes, transmettre leurs paquets figés, constater leur exécution hôte puis adopter leur résultat avant de poursuivre les gates. Ne pas déduire l'exécution de la préparation du paquet.
