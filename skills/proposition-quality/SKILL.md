---
name: proposition-quality
description: Use when a proposal direction, client document, internal handoff, or final export needs a review, especially after edits, missing evidence, self-ratings or conflicting versions.
license: MIT
---

# Vérifier une proposition

Décider sur les fichiers précis et leurs preuves. Lire [les ancrages et le reçu](references/review.md). Le barème est candidat tant qu'il n'est pas calibré humainement.

## Revue

Recevoir le paquet minimal autorisé, sa liste de fichiers/empreintes et le type de revue. Employer un contexte réellement séparé sans historique privé ; consigner le mécanisme. Sans cette capacité, déclarer le gate indépendant `BLOCKED` et rendre les observations locales comme telles.

Rendre **deux résultats séparés** à chaque étape : complétude de chaque obligation applicable ; qualité aux cinq critères 0/1/2 spécifiques au passage. Employer les contrats embarqués du principal pour les rapports d'étape et ses 81 preuves d'acceptation. Les revues de direction/client/interne s'y ajoutent ; deux contextes distincts sans verdict partagé sont requis pour le client. Chaque étape et chaque réviseur requis doivent atteindre 9/10 sans défaut bloquant. Un score ne couvre ni obligation oubliée ni version différente. Le client comprend-il la mission vendue par l'agence et la décision demandée ?

Pour la revue créative, vérifier le brief d'analyse reçu avant création, le lien des transformations aux recommandations et les signes de marque préservés. Une composition séduisante mais sans rapport avec l'enjeu ne remplit pas le contrôle.

Pour la remise finale, rendre et lire toutes les pages des PDF exacts inclus dans la portée et les diapositives du PPTX client ; vérifier le contexte compilé, les objets éditables et l'essai d'édition selon le contrat du principal, ainsi que séparation d'audience, médias et droits, géométrie, mots, sources et versions. Un fichier présent ou une auto-note n'est pas une validation.

Avant tout verdict de conservation des créations, exécuter `check-creatives RUN_DIR` selon [le contrat de préservation](../proposition-composition/references/preservation.md). Les rapports de composition/export et le verdict global bloquent sans preuve courante. Compléter par la comparaison visuelle des scènes originales avec leur placement dans les fichiers exacts ; une note élevée ne contourne pas ce contrôle.

Contrôler aussi `check-experience` aux passages créatif/composition/export/final selon [son contrat](../proposition/references/experience-evidence.md). Les critères critiques nommés dans `required_full_scores` exigent 2/2 même avec un total de 9. Une entrée belle mais une suite banale, un effet interchangeable, une action perdue ou un mobile illisible bloquent la qualité. Relire les textes avec Stop Slop puis vérifier leur sens en français, sans prétendre qu’une liste de mots juge le fond.

## Sortie

Reçu avec entrées/empreintes, rôle et isolation, type de revue, cinq observations et notes, total, obligations et preuves, défauts localisés, corrections, état et limites. Après changement, marquer les dépendants `STALE`, corriger au bon niveau puis revoir les nouvelles empreintes. Une revue interne ou un scan ne vaut pas accord de diffusion ou publication relue.
