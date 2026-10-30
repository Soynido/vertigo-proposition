---
name: proposition
description: Use when a company URL is provided for an agency proposal, a client presentation, or continuation of a proposal with client, sales and technical deliverables.
license: MIT
---

# Proposition

Construire une proposition d'agence propre à l'entreprise, depuis son URL. L'URL suffit pour commencer : rechercher les éléments accessibles, distinguer faits et hypothèses, produire le brief. Demander uniquement une décision réellement nécessaire, jamais un questionnaire de démarrage systématique.

Au collaborateur, parler simplement et brièvement : expliquer le travail utile et la décision suivante, comme à une personne non technique. Donner une nouvelle seulement lorsqu'elle apporte une information utile ; garder les IDs, outils et mécanismes internes dans les preuves. Pendant cette commande, ajouter le relevé bref temps/tokens/ressources décrit dans [les capacités](references/capabilities.md), avec « non disponibles » pour les compteurs réellement inaccessibles.

## Reprendre et travailler

1. Résoudre le dossier installé de ce SKILL comme `MAIN_SKILL_DIR`. Lire [le routage](references/workflow.md) et la dernière preuve du run. Utiliser `next-stage RUN_DIR` pour reprendre le premier passage incomplet ou périmé ; conserver les résultats encore valides. Les notes dans un fichier isolé ne remplacent pas les preuves enregistrées.
2. Exécuter le doctor et lire [les reçus de capacités](references/capabilities.md). Les quatre familles attendues sont SEO/GEO, Impeccable, Apple Design et Scroll Craft ; une famille absente reste indisponible. Adapter une méthode utile sans prétendre avoir exécuté ses outils.
3. Produire des sorties contrôlables, dans l'ordre de leurs dépendances : couverture du site et des canaux, modèle sourcé, analyses, réconciliation, **brief public explicite**, direction, **histoire et mission de l'agence explicites** selon [le contrat de montage](../proposition-story/references/argument.md), composition, revues, dossiers internes, exports et vérification. Employer un spécialiste seulement sur son besoin ; les références de ce skill permettent aussi la voie autonome.
   Avant la création, transmettre le brief issu des sources analysées, avec observations, changements recommandés, objectifs et codes de marque à préserver, selon [la passation stratégique](../proposition-strategy/references/brief.md). Pour tout nouveau prospect, suivre [le lancement créatif](../proposition-creative/SKILL.md#lancement) : lecture du contrat installé et reprise de sa capsule dans le dispatch. Explorer au moins deux mondes, rendre et comparer leurs scènes centrales, puis sélectionner avant les déclinaisons complètes. Le besoin commercial peut être le même ; le brief ne choisit pas sa réponse visuelle à la place du créatif. Une instruction externe explicite peut imposer une direction ou un nombre, avec preuve selon le contrat. Garder le format demandé ; une exploration seule ne devient pas un parcours complet validé.
4. Transmettre à la création uniquement une projection publique minimale, avec liste de fichiers et empreintes. Créatifs et réviseurs travaillent dans de nouveaux contextes sans historique privé. L'absence de cette capacité bloque le gate indépendant, pas la préparation locale autorisée.
   Au montage, charger le contrat de récit K01–K08 et [le préalable de composition](references/experience-evidence.md#plan-de-composition-préalable). Carte, plan visuel et pilote inspectés précèdent `check-experience RUN_DIR --composition-plan-only`, puis la fabrication complète. La voie publique démontre l'approche avec les propres scènes retenues, sans bibliothèque privée indispensable. Les anciennes fonctions, l'exploration avant sélection et le verrou des scènes restent requis.
5. Livrer les trois PDF séparés et leurs sources éditables d'une même révision, avec la présentation client `Proposition.pptx` et le fichier compilé `Contexte client.md`, selon [le contrat d'édition et de contexte](references/editable-delivery.md). La structure PowerPoint est modifiable ; les créations visuelles restent des images indépendantes remplaçables. Vérifier les fichiers exacts selon [le contrat qualité](references/quality.md). Une publication demande ensuite un plan exact approuvé et un readback distinct.

Une demande limitée à une exploration ou à un seul format conserve cette portée ; les sorties et gates non exécutés du parcours complet restent tels. Ne pas ajouter les dossiers internes à une demande client seule : configurer `parameters.delivery_scope: client`, selon [les preuves de récit et de progression](references/experience-evidence.md). Le mode complet reste `full`. Le mode URL seul suit le parcours complet.

## Preuve de passage

Chaque passation indique : étape, état, entrées et empreintes, décisions et sources, sorties et empreintes, obligations non prouvées, capacités réellement employées, prochain travail. Noter chaque étape selon [ses cinq critères](references/stage-quality.md) et contrôler chacune des [81 obligations](references/acceptance.md). Séparer complétude, qualité, droit de diffusion et publication. Une nouvelle source invalide les jugements et exports dépendants.

Utiliser [la CLI](references/cli.md) pour persister l'état ; ses reçus ne remplacent pas le jugement métier. Lire [le contrat commercial](references/proposal.md) avant brief/histoire/Sales. La présence de fichiers, un score isolé ou une urgence ne constituent pas une preuve finale.

## Exécution et reprise

Lire [les règles de reprise et d'exécution native](references/performance.md) dès la coordination : réserver les tâches prêtes, transmettre leurs paquets figés, constater leur exécution hôte puis adopter leur résultat avant de poursuivre les gates. Ne pas déduire l'exécution de la préparation du paquet.
