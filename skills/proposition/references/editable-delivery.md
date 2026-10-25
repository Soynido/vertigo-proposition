# Livraison éditable et contexte compilé

Ce contrat précise les sorties attendues de l'agent. Il n'annonce pas un nouvel exporteur embarqué : la CLI `export` existante produit du PDF depuis HTML/CSS. La création et le contrôle PPTX utilisent les capacités réellement disponibles de l'hôte ou un outil autorisé, dont les opérations et limites sont consignées. Une capacité absente laisse cette sortie requise `BLOCKED` ou son contrôle `NOT_RUN`, jamais PASS.

## Paquet de la présentation client

Dans le parcours complet, livrer les trois PDF séparés et leurs sources, plus ce paquet client autonome :

| Fichier | Rôle |
|---|---|
| `Proposition.pdf` | Référence visuelle de la proposition client. |
| `Proposition.pptx` | Même proposition, avec structure de présentation modifiable à la main. |
| `Contexte client.md` | Recherche utile compilée et décisions, utilisables sans la conversation. |
| `presentation.json` | Catalogue des pages, éléments et actifs, avec leurs correspondances aux objets PPTX. |
| `assets/` | Créations visuelles, photos et autres médias sélectionnés, fichiers indépendants et provenance. |
| `manifest.json` | Révision, audience, chemins relatifs, empreintes et liens source→exports→contrôles. |

Les sources HTML/CSS et aperçus page par page peuvent compléter ce paquet. Conserver les styles, polices/licences utiles et consignes d'édition. L'archive globale de projet reste interne ; le paquet à fournir au client ou à un autre outil de présentation se construit par liste blanche. Notes commerciales privées, secrets et dossiers internes ne se cachent pas dans ses commentaires, notes de présentateur, métadonnées ou actifs. Un format unique explicitement demandé garde cette portée, sans prétendre avoir rempli le parcours complet.

## Ce qui se modifie dans PowerPoint

Les titres, textes explicatifs, légendes, blocs, fonds et formes de la **présentation** sont des objets natifs séparés, sélectionnables ; les groupes utiles restent dissociables. Positions, dimensions, couleurs et organisation peuvent évoluer sans refaire toute la diapositive.

Les créations visuelles de l'agent restent des **images indépendantes** : photographie, illustration, moodboard ou maquette composée. Elles se déplacent, se redimensionnent, se recadrent et se remplacent. Leur contenu interne et leurs pixels n'ont pas à être décomposés dans PowerPoint. Conserver leurs fichiers et sources disponibles pour une nouvelle génération ou retouche. Cette distinction est le périmètre de l'édition promise.

Une image d'une maquette peut contenir ses textes d'interface ; le titre, la légende et les explications de la présentation qui l'entourent restent natifs. Une diapositive entière aplatie, ou du texte invisible ajouté par-dessus une capture, ne satisfait pas ce contrat. Une photo plein cadre en fond reste possible si les éléments de présentation superposés sont séparés.

Prévoir cette décomposition lors de la composition. Pour chaque élément du catalogue : ID stable, page, type texte/forme/image/autre objet natif, rôle, contenu ou chemin d'actif, position/dimensions, ordre, style, groupe, références de source et objet PPTX correspondant. Pour une création fixe, indiquer explicitement le périmètre `image remplaçable`. Les objets et les fichiers doivent correspondre ; un catalogue déclaratif n'est pas la preuve de leur existence.

## Contenu de « Contexte client.md »

Compiler la recherche utile, y compris les options écartées qui éclairent les choix, pas seulement résumer les pages finales. Organiser le fichier ainsi :

1. Entreprise, URL, révision, périmètre et fichiers fournis.
2. Offre, publics, voix, objectifs proposés et faits qui les soutiennent.
3. Sources explorées : site, menus/sous-menus, réseaux officiels, documents, couverture et limites ; distinguer recensé, collecté et analysé.
4. Observations et recommandations : preuve, statut factuel, changement, priorité, objectif et lien aux visuels.
5. Références de marché et qualités retenues, avec sources et limites.
6. Brief, mission d'agence, limites et décision attendue.
7. Identité préservée, direction, alternatives, arbitrages, formulations utiles et éléments à conserver ou retravailler.
8. Histoire et contenu exact par page, puis correspondance pages/éléments/actifs.
9. Médias : sujet, fichier, original/variante, provenance, droit/usage, transformation, classement authentique/fidèle/synthétique et placements.
10. Contrôles réellement effectués, versions concernées, inconnues, limites, prochaines vérifications et consignes d'édition.
11. **SOURCES/OBSERVATIONS** : registre détaillé avec identifiants stables, URL ou document d'origine, dates disponibles, observation/extrait utile, statut et utilisation ou motif d'exclusion.

Les détails techniques sourcés utiles à la reprise peuvent figurer dans ce contexte de travail ; la proposition client garde des formulations simples. Ne pas y introduire les informations privées d'agence hors autorisation de cette audience. Un contexte interne complémentaire reste dans le dossier interne. Aucune source inaccessible ou preuve manquante n'est reconstituée de mémoire ; conserver son absence.

Les chemins sont relatifs au paquet ; les médias nécessaires sont joints, pas seulement liés à une machine d'origine. Un Markdown ne contient pas les fichiers binaires qu'il référence. Ne pas promettre l'import réussi dans PowerPoint, Keynote, Gamma, Canva ou ChatGPT sans essai réel de cette destination.

## Contrôle et reprise

- Vérifier chaque élément de structure contre les objets du PPTX et les actifs du catalogue ; relever les éléments aplatis hors du périmètre image annoncé.
- Rendre et ouvrir toutes les diapositives du PPTX exact, puis les comparer au PDF : contenu, polices, cadrages, hiérarchie, géométrie et lisibilité.
- Dans une copie, modifier un titre, un bloc et un placement, puis déplacer ou remplacer un visuel ; enregistrer, rouvrir, réexporter et inspecter le résultat. Consigner l'outil et la portée réelle : une édition programmatique ne prouve pas un essai manuel dans PowerPoint.
- Vérifier la reprise depuis le seul contexte et les actifs : un lecteur doit retrouver offre, recommandations, mission, histoire, direction, sources et inconnues sans l'historique.
- Séparer fichier généré, structure vérifiée, rendu inspecté, import testé et modification/réexport testés. Le statut de l'un ne valide pas les autres.

La composition source et ses projections restent d'une même révision. Toute édition externe utile crée une nouvelle révision à réconcilier avec les sources et le contexte ; les anciennes revues ne se reportent pas automatiquement. La qualité esthétique et le droit de diffusion restent des décisions distinctes de l'édition.

L’historique éventuel dans `Contexte client.md` distingue capture, publication, consultation et limites ; il ne date pas une dernière MAJ supposée. N’y inclure que les observations autorisées issues du corpus interne, selon le contrat de découverte.
