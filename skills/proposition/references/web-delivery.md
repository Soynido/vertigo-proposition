# Livraison web depuis deux URL

Ce contrat adapte les sorties du parcours existant ; il ne remplace ni Discovery, ni Strategy, ni les quatre méthodes créatives, ni l'exploration avant sélection. L'entrée standard installée choisit `web`. Une demande documentaire explicite choisit `documents` à l'initialisation. Le format est immuable ; une reprise historique sans champ de format reste documentaire.

## Préparation et départ

L'installation prépare une fois Python, navigateurs Chromium/WebKit, méthodes verrouillées, ressources agence et publication. Le propriétaire configure sa connexion Vercel et son profil privé, sans droit d'écriture sur le dépôt du kit. Aucun MCP ou fournisseur IA payant supplémentaire n'est obligatoire. Ne pas lancer une proposition pour terminer une installation manquante ; qualifier les capacités dans un contexte neuf avant l'essai client. Lire [le starter](installation.md).

Dans une nouvelle tâche ne recevant que les deux URL, retrouver le launcher installé et le profil privé depuis `.vertigo/setup.json`. Si le transport natif est activé, appliquer [son démarrage dans la lane](native-startup.md) avant init ; seul le worker identifié initialise ensuite le run avec `--delivery-format web`, sous `WORKSPACE/outputs/runs`. Consigner révision, arbre et inventaire réellement installés ; ne pas changer de version ou de ressources en cours de test. Exécuter `doctor --delivery-format web` puis `web preflight RUN` : cette lecture vérifie outils de publication, accès actuel et projet sans écriture fournisseur. Vérifier les capacités essentielles de recherche, navigation rendue, lecture des images, contextes indépendants et publication. Une absence essentielle bloque son passage, sans faux repli ou modèle imposé.

Les tâches natives de [l'exécution](performance.md) restent disponibles. Deux tâches indépendantes simultanées au maximum, un prospect en qualification à la fois. Le coordinateur conserve l'adoption et l'état ; les workers rendent des candidats, sans approuver ou publier leur propre travail.

## Sources et matière disponible

Discovery conserve ses menus, bandeaux, scroll, mobile, canaux, recherches publiques Google/Ads/Meta/avis et replis. Strategy lit les deux méthodes publics/besoins puis réalise ses missions utiles avant réconciliation. Concurrents de marché, résultats observés et références de création ne deviennent pas une même catégorie. Aucune position, acquisition, préférence utilisateur, donnée privée ou promesse chiffrée n'est déduite d'une absence de fournisseur.

En web, Discovery fournit aussi les médias réutilisables : images et vidéos natives, sources/posters, pages d'origine et observations réseau utiles. Une miniature ne prouve pas une vidéo ; un média inaccessible reste inaccessible. Sélectionner les fichiers utiles, télécharger en flux dans le run avec limites explicites, contrôler leur contenu et leur décodage, puis enregistrer source publique et artefact lié. Les workers peuvent rendre cet inventaire et les fichiers dans leur arbre de sources ; leur adoption et leur enregistrement appartiennent au coordinateur. Ne pas envoyer de binaires/base64 dans les journaux. Ne pas télécharger aveuglément tout un catalogue.

Conserver URL, date, octets, SHA256, sujet, statut authentique/transformé/généré, transformation et droits. Le public accessible n'est pas une licence de réutilisation. Ajouter les références d'artefacts retenus à `creative-inputs.media_refs` ; les compléments publics explicites vont dans `supporting_public_refs`. Les faits et preuves cités doivent rester vérifiables dans les sources figées. Les données privées et anciens projets prospect ne sont pas un paquet créatif.

Après le gate `brief.public`, `web release RUN` fige la projection autorisée des entrées. Elle s'appuie sur les sources publiques et la revue du brief ; elle ne fabrique pas une approbation humaine. `context-packet` ou les paquets natifs transmettent ces fichiers, leurs méthodes et références exactes. Le protocole natif ajoute la table des preuves publiques et la correspondance artefact→fichier reçu ; les bruts internes ne deviennent pas des fichiers publiables.

## Création puis développement dans le même contexte

Le [contrat créatif](../../proposition-creative/references/creative-contract.md), sa capsule et les quatre méthodes parviennent à un créateur neuf, sans historique privé ou scénario gagnant. Réception → lecture réelle et reçu → contrôle des entrées → au moins deux mondes distincts rendus et inspectés → comparaison puis sélection → développement des directions retenues dans ce même contexte. Les vues d'une seule idée ne sont pas plusieurs mondes. La sélection et les scènes statiques restent figées avant leur transposition.

Faire vivre le produit ou le service à un public étayé : matière disponible → concept → progression contrôlée par le visiteur → interaction → action utile. L'entrée et les sections immersives doivent révéler quelque chose de propre à ce client. Le mouvement organise le sens, le rythme et la découverte ; une photo qui se déplace ne suffit pas par sa seule présence. Ni la structure en quatre scènes, ni une horloge, ni la DA d'un témoin ne sont universelles.

Le créateur continue jusqu'à la spécification et au HTML. Lire les mécanismes reçus dans `proposition/resources/web/README.md` lorsqu'ils sont appliqués. Progression, couches, révélations, animation photo et lecture vidéo sont portables ; un mécanisme spécifique reste possible avec raison et preuves. Le moteur ne choisit pas le concept. Conserver les propres médias et signes du prospect ; ne pas réduire silencieusement la direction aux effets déjà disponibles.

Le paquet `resources/web/agency` fournit logo, polices autorisées, habillage commercial et références studio. Son CSS est limité au cadre agence. Le poster studio reste une image fixe, les références sont attribuées ; aucun film joué ou résultat client n'est déduit de leur présence. L'expérience prospect garde sa propre identité. Les scènes du projet peuvent expliquer l'approche sans portfolio obligatoire.

## Plan d'expérience préalable

Préparer un JSON conforme à `contracts/web-plan.schema.json`, puis appeler avant d'écrire la homepage :

```bash
python3 MAIN_SKILL_DIR/scripts/proposition.py web plan RUN --source SITE_DIR --plan PLAN.json
```

Il relie les empreintes du brief et de la sélection à :

- K01–K08 : compréhension, preuve/opportunité, mécanisme, scénario, transformation, intérêt/mesure, mission et décision ; sélecteurs, preuves et statuts des affirmations. Huit fonctions, pas huit sections obligatoires.
- Scènes : sens, interaction, intentions visuelles gelées consommées, fichiers médias, états début/intermédiaire/fin, mobile et mouvement réduit.
- Moteur : fichiers réellement utilisés, mécanisme portable ou spécifique, empreintes des ressources reçues et raison de l'adaptation.
- Actions : celles du prospect avec leurs destinations prouvées, et décision commerciale distincte envers Vertigo.
- Liste publique de fichiers, page des sources/crédits et droits par média.

K03 décrit le mécanisme montré ; K06 distingue effet envisageable, indicateurs acquisition/conversion et données disponibles/inconnues ; K07 donne scope, inclusions/exclusions/conditions ; K08 précise l'accord demandé. Le [contrat commercial K01–K08](../../proposition-story/references/argument.md) reste la référence de sens.

Le reçu du premier plan ne régularise pas une homepage déjà écrite. La version est conservée. Une correction de plan exige `--supersedes SHA256 --reason RAISON`, conserve les destinations réservées et n'autorise aucune nouvelle sélection silencieuse. Une correction de code conforme au même plan ne demande pas une autre exploration.

## Build et contrôles exacts

```bash
python3 MAIN_SKILL_DIR/scripts/proposition.py web build RUN --source SITE_DIR --plan PLAN.json
python3 MAIN_SKILL_DIR/scripts/proposition.py web inspect RUN
```

La homepage est `index.html` à la racine du déploiement ; c’est cette URL racine qui est remise et contrôlée. Le build statique HTML/CSS/modules JavaScript reçoit seulement sa liste autorisée. Manifestes privés, profils, caches et journaux restent hors du site servi. La source éditable, les médias, le concept et les preuves identifient les mêmes octets. Le gel des intentions ne consiste pas à aplatir une scène en capture d'écran pour remplacer une vraie interface.

Pour un film H.264 natif consommé par le décodeur portable, `web media-index RUN --source FILM.mp4 --output FILM.mp4.frames.json` indexe les octets inchangés. Conserver film et index ensemble. Codec ou outil indisponible : signaler la limite et examiner un mécanisme compatible ; ne pas transformer un film en quelques images et prétendre conserver son immersion.

L'inspection contrôle les fichiers gelés, Chromium et WebKit, desktop 1440×900, fenêtre 1280×600, mobile 390×844 et mouvement réduit. Examiner les états intermédiaires, l'aller/retour, les actions, le clavier, le décodage et les erreurs. Les actions déclarées sont activées au clic et à Entrée avec contrôle d’éligibilité clavier ; une destination externe est interceptée sans l’ouvrir, son fonctionnement distant reste hors de cette preuve. Le serveur local fournit les plages d’octets nécessaires au lecteur de films, sans charger un gros film entier pour un paquet. Le rapport produit des preuves mécaniques et des captures ; il n'accorde aucune note esthétique. Les scènes, fonctions et actions peuvent désigner leur `page` publique (homepage par défaut) ; chaque HTML publié est ouvert, les médias intégrés sont aussi contrôlés dans leurs frames. Les contrôles déclarés gardent `selector`, `expect_selector` et éventuellement `key`. Les réviseurs doivent ouvrir les vrais HTML et inspecter tous les états et pages de la portée, y compris les éléments intégrés ou plein écran lorsqu'ils existent.

Deux réviseurs client indépendants reçoivent le build exact, ses captures, les intentions sources, le brief et les preuves nécessaires, sans historique privé ni verdict partagé. Garder les mêmes critères et seuils, les observations localisées et les scores critiques 2/2. Qualité créative, vérité, utilité commerciale, complétude et diffusion restent distinctes. Pas de PASS depuis un moteur, une note auteur ou la présence de fichiers. Un cycle de correction est prévu dans le budget ; réexaminer les défauts bloquants et les contrôles affectés, sans relancer les recherches et créations encore valides.

## Publication et remise

Après les gates applicables et les deux revues, `web publish RUN` utilise la politique privée configurée à l'installation. Le projet n'est ni créé ni reconfiguré pendant le run. Chaque build accepté reçoit une URL de prévisualisation distincte, sans changer domaine, alias ou site existant. Une issue inconnue impose recherche et réconciliation, jamais une répétition aveugle.

`web verify RUN` contrôle les métadonnées du déploiement, tous les octets publics et de nouveaux contextes navigateur sans authentification. Une page de connexion ou un mauvais build bloque. Une preuve navigateur encore valide est réutilisée avec un nouveau readback réseau ; son heure de première remise ne change pas. Un contrôle navigateur public bloqué peut être rejoué dans le budget sur le même build, en conservant les preuves échouées ; il ne crée pas une première remise réussie. Une preuve modifiée n’est pas régularisée par ce replay. Une capture modifiée ou une nouvelle révision impose les contrôles affectés.

Remettre le lien public exact, les sources éditables et crédits, le concept et l'opportunité en mots simples, ainsi que verdicts et limites. Ne pas envoyer au prospect le paquet interne de preuves. Ni PDF/PPTX, ni dossiers Sales/technique ne sont exigés par le mode web. Une demande `documents` conserve leurs contrats et contrôles intacts ; le passage technique hérité `export.documents` désigne le build/contrôle web lorsqu'un run est web.

## Durée et qualification

Objectif 600 secondes jusqu'au lien vérifié et remis, avec recherche, création, développement, revues, corrections et publication ; plafond de qualification 1 200 secondes, checkpoint conservé. Aucun nouveau dispatch après le plafond. `web budget RUN` mesure l'écoulé depuis `init`, sans remise à zéro par étape ou reprise. Si l'objectif est dépassé, conserver `FAIL_TIMING` même quand le site et le lien passent leurs contrôles.

Le temps avant `init` et jusqu'au message final doit aussi être mesuré depuis les horodatages réels du tour hôte pour qualifier le délai complet. S'ils ne sont pas exposés, cette partie reste inconnue ; le seul chronomètre interne ne prouve pas les 600 secondes depuis la demande. Installation initiale, phases instrumentées, attentes et portions non instrumentées restent séparées. Tokens/coût individuels ou RAM totale inconnus ne sont pas inventés ; un quota de compte est partagé.

Les [règles de préintégration et de qualification](../../proposition-quality/references/production-validation.md) restent applicables au kit : composants, contrats distribués, revue/code/suite à la promotion, puis E2E neuf avec exactement les deux URL et sans coaching. Le témoin de qualité reste hors du contexte du créateur. Un essai assisté, un lien technique ou un cas réussi ne démontrent pas la répétabilité ni la qualité universelle.
