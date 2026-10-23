# Préserver les créations retenues au montage

Ce contrôle complète la passation de direction. Il ne change ni le contrat créatif ni sa capsule. Il intervient **après les scènes rendues et leur comparaison, avant le montage**, puis sur les fichiers finaux. Il ne relance pas la découverte ou la création.

## 1. Figer ce qui doit rester

Le propriétaire reprend toutes les directions encore proposées, les vues desktop/mobile et prolongements effectivement retenus. Un choix laissé ouvert reste ouvert : le compositeur ne sélectionne pas silencieusement une direction. Ne pas annoncer trois mobiles si une seule vue mobile a été produite. Tout retrait demandé par le client ou le propriétaire doit être explicite et sourcé dans la décision ; l'agent de montage ne se donne pas cette autorité.

Produire dans le run un JSON de sélection, puis appeler :

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py freeze-creatives RUN_DIR selection.json
```

Exemple fictif, chemins relatifs au run :

```json
{
  "revision": "creative-r1",
  "actor": "run-owner",
  "decision": "Les deux pistes restent proposées au client ; aucune sélection finale.",
  "retained": [
    {"id": "direction-a-desktop", "path": "creative/a-desktop.png", "role": "desktop", "crop": [0,0,1,1], "min_page_fraction": 0.15},
    {"id": "direction-b-mobile", "path": "creative/b-mobile.png", "role": "mobile", "crop": [0,0,1,1], "min_page_fraction": 0.15}
  ]
}
```

Le verrou conserve les empreintes réelles, le run et la décision. Les scènes sont des PNG/JPEG/WebP rendus ; conserver leurs sources créatives séparément. Le recadrage approuvé est `[gauche, haut, droite, bas]`, en fractions de l'image originale ; au moins la moitié reste visible. La fraction minimale de page est fixée avant montage (défaut 15 %, minimum 10 %), pas abaissée pour faire passer une miniature. Les marges du board peuvent être exclues **avant** verrouillage ; le montage ne change pas cette décision.

Le verrou est à écriture unique. Ne pas le supprimer ni réécrire les métadonnées pour contourner un échec. Une révision créative explicitement autorisée exige une nouvelle révision de run avec reprise des preuves encore valides ; elle n'impose pas de nouveau crawl. Le contrôle n'authentifie pas l'autorité humaine d'un acteur déclaré : la décision sourcée reste à revoir.

## 2. Relier les scènes aux deux exports

Composer depuis les fichiers figés, comme images indépendantes. Ne pas les redessiner, aplatir toute la slide, remplacer un mobile par un schéma ou réencoder les fichiers retenus. Garder les textes et la structure du deck natifs éditables autour des visuels.

Pour le gate de composition, produire les deux exports client candidats depuis la source stabilisée. Le passage `export.documents` reprend ces mêmes octets s’ils sont inchangés, sinon il recontrôle les nouveaux exports ; les dossiers internes n’ont pas besoin d’être produits prématurément.

Enregistrer les fichiers finaux avec les IDs **`client-pdf`** et **`client-pptx`**, puis un manifeste de placements comme artefact interne **`creative-placements`** :

```json
{
  "pdf": "outputs/client/Proposition.pdf",
  "pptx": "outputs/client/Proposition.pptx",
  "placements": [
    {"creative_id": "direction-a-desktop", "page": 6, "rect": [0.08,0.18,0.84,0.7], "pptx_shape_id": "12"},
    {"creative_id": "direction-b-mobile", "page": 7, "rect": [0.35,0.15,0.3,0.7], "pptx_shape_id": "8"}
  ]
}
```

`page` est numérotée depuis 1, identique dans PDF et PPTX. `rect` désigne `[x,y,largeur,hauteur]` en fractions de page, origine en haut à gauche, **image visible seulement**, sans cadre. `pptx_shape_id` est le `p:cNvPr/@id` réel de l'image sur cette slide. Les rectangles doivent respecter le ratio du recadrage conservé ; les chiffres d'exemple ne sont pas des placements valides pour toutes les images.

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py artifact RUN_DIR client-pdf outputs/client/Proposition.pdf --audience client
python3 <MAIN_SKILL_DIR>/scripts/proposition.py artifact RUN_DIR client-pptx outputs/client/Proposition.pptx --audience client
python3 <MAIN_SKILL_DIR>/scripts/proposition.py artifact RUN_DIR creative-placements composition/placements.json --audience internal
python3 <MAIN_SKILL_DIR>/scripts/proposition.py check-creatives RUN_DIR
```

## 3. Contrôle bloquant

Les rapports `creative.direction` exigent le verrou courant. `client.composition`, `export.documents`, `validate` et la préparation du paquet final recalculent la consommation : aucun reçu PASS déclaratif ne remplace la vérification des fichiers.

Le contrôle bloque si sélection absente/modifiée, scène changée/omise, export non courant, manifeste pointant un autre fichier, zone trop petite/hors page, chevauchement, pixels PDF trop différents, image PPTX remplacée/masquée, recadrage différent ou objet ultérieur pouvant la couvrir. Une scène répétée est autorisée, chaque occurrence déclarée est vérifiée. Les slides masquées, images avec remplissage décalé/réduit, géométries non rectangulaires, contours peints, placements groupés, tournés ou effets non pris en charge restent bloqués : utiliser une image indépendante et simple, sans relancer la DA.

PDF : comparaison des pixels rendus avec le recadrage figé, tolérance moyenne globale de 3,5 %, complétée par une comparaison locale sur des tuiles de 10 × 10 d’une vue normalisée à 240 × 240 (erreur locale maximale 10 % après léger flou pour le rééchantillonnage/anticrénelage) ; c'est un contrôle de fidélité visuelle, pas une identité mathématique des pixels. PPTX : empreinte exacte du média, ordre réel des slides, relation image, position, taille, crop et visibilité structurelle. Ces contrôles ne remplacent pas le rendu et l'inspection de toutes les diapositives exactes : logiciels, effets ou états non pris en charge peuvent différer.

Corriger uniquement le montage ou le manifeste erroné, réexporter, réenregistrer les nouvelles empreintes puis relancer le contrôle et les revues dépendantes. Ne pas fabriquer de nouvelles créations pour satisfaire ce gate. Une ancienne version de run sans verrou est bloquée tant que cette passation n'est pas faite.

Le PASS porte sur la conservation des scènes, jamais sur la qualité, les droits, la valeur commerciale, l'autorisation d'envoyer ou la complétude du pipeline. Les notes d'étape restent nécessaires et ne compensent pas un échec mécanique.
