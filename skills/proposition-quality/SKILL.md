---
name: proposition-quality
description: Use when a proposal needs review, or when repository skills, contracts, workflow or runtime changes need production qualification, especially after assisted tests, self-ratings or conflicting versions.
license: MIT
---

# Vérifier une proposition

Décider sur les fichiers précis et leurs preuves. Lire [les ancrages et le reçu](references/review.md). Le barème est candidat tant qu'il n'est pas calibré humainement.

## Validation production du repo

Pour une étape, un skill ou un contrat nouvellement figé, modifié ou intégré, appliquer [la validation production sans accompagnement](references/production-validation.md), avec sa fiche préalable avant tout nouveau POC. Les essais indépendants d'une capacité servent à la qualifier avant intégration ; la promotion exige ensuite un E2E neuf recevant uniquement **URL REPO + URL SITEWEB**, sans consigne de création ajoutée par le mainteneur. Cette règle s'applique aussi à ce skill de validation : son contrôle documentaire ne vaut pas validation E2E du repo.

Ce mode concerne la maintenance d'une version du kit. Une simple exécution de proposition, son brief client ou le gel de ses images ne déclenchent pas un autre test E2E récursif.

Après un essai manuel, reprendre la matrice existante selon la section **Continuité après un essai manuel** de cette référence : toutes les capacités gardent portée, responsable, preuve, état et prochaine action. Vérifier son checkpoint avec `scripts/check_integration.py` à la reprise et avant passation ; `--close` bloque la clôture du plan parent tant qu'une ligne reste ouverte. Une réparation voisine terminée ne ferme pas les intégrations restantes. Ce contrôle de maintenance ne s'ajoute pas aux runs client.

## Revue

Recevoir le paquet minimal autorisé, sa liste de fichiers/empreintes et le type de revue. Employer un contexte réellement séparé sans historique privé ; consigner le mécanisme. Sans cette capacité, déclarer le gate indépendant `BLOCKED` et rendre les observations locales comme telles.

Rendre **deux résultats séparés** à chaque étape : complétude de chaque obligation applicable ; qualité aux cinq critères 0/1/2 spécifiques au passage. Employer les contrats embarqués du principal pour les rapports d'étape et ses 81 preuves d'acceptation. Les revues de direction/client/interne s'y ajoutent ; deux contextes distincts sans verdict partagé sont requis pour le client. Chaque étape et chaque réviseur requis doivent atteindre 9/10 sans défaut bloquant. Un score ne couvre ni obligation oubliée ni version différente. Lire [le contrat de montage](../proposition-story/references/argument.md). Localiser la preuve, le changement montré, la conséquence pour le visiteur, le travail de Vertigo et la décision. Le critère `story` de composition exige 2/2 : une présence de rubriques ou un catalogue de scènes ne suffit pas.

Pour la revue créative, vérifier le brief d'analyse reçu avant création, le lien des transformations aux recommandations et les signes de marque préservés. Une composition séduisante mais sans rapport avec l'enjeu ne remplit pas le contrôle.

Pour le KIT, recevoir carte K01–K08, reçu préalable, plan visuel/pilote, catalogue et exports exacts de même révision. Localiser le mécanisme montré, le scénario d'ensemble, la comparaison de la même tâche, l'effet envisagé et sa mesure/inconnue, la mission avec limites et la décision. Les huit anciens rôles ne prouvent pas à eux seuls ces fonctions. Confronter la chronologie aux opérations réelles ; une date déclarée n'est pas une attestation. Inspecter aussi l'habillage autour des scènes : le deck sert ce client, sans gabarit universel ni variations décoratives obligatoires. Une bonne page centrale ne couvre pas les raccords absents. Le contrôle préalable et les tests moteur ne certifient ni le WOW ni l'autonomie du parcours.

Pour la remise finale, rendre et lire toutes les pages des PDF exacts inclus dans la portée et les diapositives du PPTX client ; vérifier le contexte compilé, les objets éditables et l'essai d'édition selon le contrat du principal, ainsi que séparation d'audience, médias et droits, géométrie, mots, sources et versions. Un fichier présent ou une auto-note n'est pas une validation.

Avant tout verdict de conservation des créations, exécuter `check-creatives RUN_DIR` selon [le contrat de préservation](../proposition-composition/references/preservation.md). Les rapports de composition/export et le verdict global bloquent sans preuve courante. Compléter par la comparaison visuelle des scènes originales avec leur placement dans les fichiers exacts ; une note élevée ne contourne pas ce contrôle.

Contrôler aussi `check-experience` aux passages créatif/composition/export/final selon [son contrat](../proposition/references/experience-evidence.md). Les critères critiques nommés dans `required_full_scores` exigent 2/2 même avec un total de 9. Une entrée belle mais une suite banale, un effet interchangeable, une action perdue ou un mobile illisible bloquent la qualité. Relire les textes avec Stop Slop puis vérifier leur sens en français, sans prétendre qu’une liste de mots juge le fond.

## Sortie

Reçu avec entrées/empreintes, rôle et isolation, type de revue, cinq observations et notes, total, obligations et preuves, défauts localisés, corrections, état et limites. Après changement, marquer les dépendants `STALE`, corriger au bon niveau puis revoir les nouvelles empreintes. Une revue interne ou un scan ne vaut pas accord de diffusion ou publication relue.

## Exécution et reprise

Contrôler [les preuves d'exécution et de reprise](../proposition/references/performance.md) : identités réelles, paquets/lectures liés aux empreintes, verdicts propres aux fichiers et validité courante. Un reçu historique ne réactive aucun résultat périmé ; les contrôles techniques ne prouvent pas la qualité créative.
