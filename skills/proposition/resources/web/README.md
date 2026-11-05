# Mécanismes web portables — version 1

Ces modules fournissent une horloge de scroll, des couches animées et le décodage de films existants. Ils ne fournissent ni concept, ni composition, ni nombre de scènes, ni identité de prospect. La spécification retenue décide des médias, transformations, transitions, actions et adaptations. Un mécanisme particulier reste possible lorsqu'il est justifié et vérifié.

## Photos, couches et révélations

`createScrollScene(element, {layers, onUpdate})` dans `motion.mjs` lie une section réelle à la progression native du document. Chaque couche fournit son `element`, ses `keyframes` Web Animations et ses éventuelles `options`. La progression est normalisée entre le haut de la section et sa fin de défilement. `onUpdate` reçoit `{progress, reducedMotion, active, width, height}`. Le DOM, le contenu et la géométrie restent ceux du concept.

Le résultat expose `progress`, `goTo(progress)`, `refresh()` et `destroy()`. Le retour utilise la même horloge que l'aller. Les interactions clavier et tactiles, le zoom et les liens natifs restent disponibles. La préférence de mouvement réduit annule les effets des couches et restaure le HTML/CSS sous-jacent. Prévoir explicitement sa mise en page, son poster et son accès aux informations/actions ; l'annulation d'un effet ne les invente pas.

Les mises à jour se font lors des changements de scroll, de taille ou de préférence ; il n'y a pas de boucle d'animation permanente pour une section immobile. Détruire le contrôleur quand sa page est retirée.

## Films : préparation et présentation distinctes

`proposition_runtime.web.index_film(source, output)` prépare avec `ffprobe` un index `<film>.mp4.frames.json` des paquets H.264 inchangés. Il vérifie la source, les positions, les temps et les images clés. Il ne télécharge, ne transcode et ne remplace aucun film. Une reprise identique réutilise l'index ; une autre source exige une nouvelle destination. Un index périmé empêche le build.

`createScrollFrames(source, signal, present, failed, read, options)` dans `scroll-frames.mjs` reprend le décodeur des références hachées. `createMediaReader(source)` fournit une lecture HTTP par plages bornée. Le callback `present({image, time})` reçoit une `VideoFrame` à dessiner immédiatement dans le canvas du concept ; ne pas la conserver. Le contrôleur expose `duration`, `seek(seconds)`, `suspend()`, `destroy()` et les compteurs `stats`. Suspendre les scènes hors champ ou en mouvement réduit et détruire les contrôleurs à la fermeture. Le signal d'annulation libère aussi leurs ressources.

Le temps demandé vient de la progression définie dans la spécification. Le film ne devient pas l'horloge du scroll. Conserver un poster fidèle et un accès natif à la lecture, au son et aux actions utiles selon le concept. Une animation de photo n'est pas une preuve de lecture vidéo.

Limites explicites : H.264 indexé seulement ; WebCodecs peut être indisponible ou refuser un codec. La fonction retourne alors `null`, ou appelle `failed` après une erreur. Le consommateur doit afficher et consigner le repli réellement proposé, puis le faire examiner ; aucune équivalence immersive n'est déduite. Le décodeur conserve au plus 24 surfaces décodées partagées entre ses lecteurs et, par lecteur, 8 Mio de paquets encodés par défaut (16 Mio maximum configurable). La lecture refuse une réponse complète de plus de 8 Mio si le serveur ignore Range. Ces limites de tampons ne mesurent pas la RAM totale du navigateur.

## Build et inspection

Copier les modules effectivement utilisés dans la liste publique du build, avec leur licence. Conserver leurs empreintes et documenter les adaptations. Les médias et les polices ont leur propre provenance et leurs droits ; la licence du mécanisme ne les couvre pas.

`web build` produit le build statique à partir de la liste autorisée. `web inspect` contrôle ce build exact dans Chromium et WebKit, aux tailles prévues, puis en mouvement réduit. Une sonde limitée à un navigateur ne qualifie pas l'autre. Un moteur absent produit un reçu bloqué ; `--retry` crée une nouvelle tentative sans écraser la précédente. Les captures conservent l'état animé réellement demandé. Leur altération, celle du build ou de ses sources invalide leur utilisation.

Ces contrôles mécaniques ne donnent ni note esthétique, ni avis client, ni autorisation de publication. La revue indépendante examine la réalisation exacte du concept, les transitions, la lisibilité, l'histoire et l'utilité commerciale. Les instructions canoniques de passation et de livraison appartiennent aux skills concernés.
