# Preuves d’acceptation par obligation

Ce guide précise une preuve minimale générique pour chacun des identifiants stables du registre embarqué. Il ne copie pas une matrice privée et ne fournit aucune valeur de profil privé. Lire l’exigence et son applicabilité dans `scripts/proposition_runtime/data/requirements.json` depuis le dossier du skill principal ; si une valeur/configuration manque, conserver son absence, sans inventer de défaut privé ni obtenir un PASS par l’existence d’un fichier.

Pour chaque obligation : identifiant, applicabilité motivée, état, observation, fichier/zone précise, empreintes d’entrée/sortie, défaut et correction, date du recontrôle. Une preuve ci-dessous est un minimum à contextualiser, pas un mot-clé à trouver. L’étape reçoit aussi son propre rapport à cinq critères ; cette note ne compense aucune case obligatoire non prouvée.

| ID | Obligation générique | Preuve minimale contrôlable |
|---|---|---|
| R01 | Entrée et périmètre | Run lié à l’URL, capacités/bindings utilisés et limite additive explicite ; aucun élargissement de mandat. |
| R02 | Trois audiences et sources | Manifeste des trois PDF distincts, du PPTX client à structure modifiable, du contexte compilé et des sources/médias nécessaires ; empreintes et audience de chaque fichier. Une portée explicitement limitée n'est pas présentée comme une livraison complète. |
| R03 | Limite client | Comptage des pages du PDF client exact comparé au paramètre actif ; l’édition ne compte pas les trois dossiers comme trois pages. |
| R04 | Responsable confirmé | Identité/rôle de remise confirmé par source autorisée, distinct de l’acteur invocateur ; absence conservée comme blocage. |
| R05 | Upstream réellement employés | Inventaire commits/licences/dépendances et reçus native/adapted/unavailable avec références lues, opérations et sorties. |
| R06 | Identité officielle | Fichiers de logo/identité autorisés avec origine, usages et contrôle de fidélité ; DA propre au client. |
| R07 | Compréhension de l’entreprise | Modèle V2 avec offre, publics, contexte et action souhaitée ; chaque proposition d’objectif est distinguée d’un fait. |
| R08 | Navigation rendue | Captures et journal d’interactions desktop/mobile : ouverture des menus/sous-menus, défilement et issues constatées. |
| R09 | Couverture qualifiée | Registre reliant chaque entrée à destination/tentative/issue, capture et profondeur d’analyse ; les trous restent visibles. |
| R10 | États significatifs | Inventaire des états révélés, mobiles, navigation, contenu et parcours utiles ; preuve rendue et limites pour chacun. |
| R11 | Références de marché | Comparables choisis avec rôle et source ; qualités retenues reliées au cas, sans reprise d’identité tierce. |
| R12 | Fait, proposition, inconnu | Affirmations décisives avec statut, source/date/portée ; hypothèses et limites visibles, sans résultat inventé. |
| R13 | Constat, idée, bénéfice | Page ou chaîne de pages identifiant observation, transformation proposée et bénéfice soutenable, avec preuve ou condition. |
| R14 | Langue du lecteur | Revue localisée des termes et phrases ; le lecteur peut reformuler offre, enjeu et mission sans explication orale. |
| R15 | Séparation client | Paquet client seul inspecté : aucun montant interne, note, commentaire, contact privé ou actif hors projection autorisée. |
| R16 | Équilibre de composition | Bilan du récit et des surfaces visuelles utiles à taille finale ; comparaison à la cible configurée, sans comptage artificiel de caractères. |
| R17 | Ratio photographique | Placements et surfaces visibles par livrable, classifications et calcul du ratio actif ; incertitudes de mesure explicites. |
| R18 | Sujet factuel fidèle | Comparaison des médias à leurs sujets/sources ; scène synthétique étiquetée, aucune représentation fabriquée annoncée authentique. |
| R19 | Traçabilité des actifs | Registre de chaque actif : sujet, source, droit/usage, fichier, transformations et placements ; provenance et permission séparées. |
| R20 | Options matérialisées | Brief d'analyse transmis ; visions réellement rendues et inspectées avant comparaison, lien aux recommandations, signes préservés, choix ou alternatives et compromis datés ; une option décrite seulement reste non produite. |
| R21 | Desktop et mobile utiles | Vues complètes et lisibles montrant des moments pertinents, composition mobile distincte et rôle de chaque vue dans la démonstration. |
| R22 | Playbook de la mission | Dossier Sales où vendeur, acheteur, mission d’agence et décision sont explicites ; questions, preuves et objections propres au projet. |
| R23 | Actions suivables | Chaque prochaine action a rôle, déclencheur, entrée/preuve, résultat attendu, trace de suivi et condition d’arrêt. |
| R24 | Contexte privé autorisé | Si utilisé : source d’autorisation et champs projetés, paquet exact transmis et empreintes ; sinon non-applicabilité motivée par absence d’usage. |
| R25 | Apports préservés | Observations et documents fournis identifiés comme entrées, attribués, datés et distingués des vérifications propres. |
| R26 | Transmission de l’existant | Dossier technique reliant système observé, périmètre, décisions, dépendances, limites et critères d’acceptation au projet final. |
| R27 | Continuité de l’existant | Si refonte : inventaire des contenus/fonctions/adresses à conserver et propositions de correspondance ; pertes justifiées et non masquées. |
| R28 | Prestataires et services | Si présents : fournisseurs/intégrations sourcés, responsabilités et dépendances ; périmètre de mission adapté sans fournisseur deviné. |
| R29 | Base interne configurée | Référence au paramètre privé autorisé et à sa version pour l’estimation interne ; aucune valeur par défaut inventée ou publiée côté client. |
| R30 | Service récurrent cadré | Si proposé : paramètre privé autorisé, contenu, exclusions, cadence et limites explicites dans le dossier interne seulement. |
| R31 | Calibration de l’effort | Base et calibration configurées, calcul explicite et contrôle qu’une accélération n’est pas comptée deux fois ; inconnues gardées. |
| R32 | Temps distingués | Estimation interne sépare travail actif, attente externe et validation ; hypothèses et dépendances sont nommées. |
| R33 | Plan exact de persistance | Si écriture envisagée : contenu exact de chaque opération, destination, identifiant/déduplication, effets et empreinte du plan. |
| R34 | Accord opposable | Si écriture envisagée : acteur, preuve d’accord explicite et hash du plan courant ; changement du plan invalide l’accord. |
| R35 | Capacité autorisée | Si écriture : reçu du connecteur et compte réellement autorisés ; faux adaptateur identifié comme test, jamais succès réel. |
| R36 | États relus distincts | Après écriture autorisée : preuve de relecture avec enregistrement, éligibilité et consommation séparés ; état inconnu maintenu. |
| R37 | Effet partiel ou incertain | Journal par opération, clé d’idempotence, recherche/readback avant retry et absence de doublon ou écrasement destructif. |
| R38 | Toutes les pages inspectées | Rendus et observations de chaque page des trois PDF exacts, plus board et vues requis ; aucun échantillon final implicite. |
| R39 | Deux revues isolées | Deux reçus de contextes distincts sans historique auteur ni verdict partagé, paquet/empreintes identiques et jugements indépendants. |
| R40 | Identité des fichiers validés | Manifestes source→export→revue liés aux versions et empreintes ; toute modification rend les preuves dépendantes STALE. |
| R41 | Mandats séparés | Pour chaque effet externe : autorisation correspondant à cet acte, contenu/destinataire et portée ; installation ou brouillon ne vaut pas mandat. |
| R42 | Permissions et secrets | Contrôle des accès et du paquet exact distribué ; aucun secret ou contenu privé hors audience ; limites du scan explicites. |
| R43 | Modèle réellement observé | Préférence configurée et modèle réellement employé avec provenance ; indisponibilité déclarée, aucune exécution supposée. |
| R44 | Durée mesurée | Horodatages ou durée locale mesurée avec portée ; aucun délai automatique arbitraire ajouté au processus. |
| R45 | Économie mesurable | Mesures attribuables et comparables avec provenance, unité et limites ; aucune économie calculée à partir de compteurs incompatibles. |
| R46 | Checkpoint ressources | Si seuil applicable atteint : mesure source, état/artefacts sauvegardés et décision avant opération coûteuse ; seuil inconnu non inventé. |
| R47 | Télémétrie disponible | Messages accompagnés uniquement des mesures réellement accessibles et sourcées ; canal de mesure distinct du contenu client. |
| R48 | Inconnues de mesure | Valeurs indisponibles marquées inconnues, unités non converties sans méthode et provenance ; aucune précision simulée. |
| R49 | Reprise bornée | Dernier reçu valide, dépendances périmées et accords encore applicables identifiés ; reprise au manque actif sans rejeu aveugle. |
| R50 | Réemploi sans gabarit | Cache de faits sourcés/dates réutilisé avec limites ; comparaison montre une direction et un récit propres au nouveau client. |
| R51 | Frontière fournisseur | Reçu des outils/abonnements autorisés ; arrêt à leur limite, sans bascule payante ni service non mandaté. |
| R52 | États de capacité honnêtes | Chaque annonce distingue documentation, disponibilité exposée, essai réalisé, résultat observé et déploiement réel. |
| R53 | Type et date des sources | Source originale ou secondaire identifiée, date de publication/observation, extrait précis et limites de validité. |
| R54 | Passation réutilisable | Paquet autonome de projet, dépendances et prochaine action ; aucun lancement d’implémentation ou déploiement déduit de sa remise. |
| R55 | Local et métier séparés | Checkpoint local avec emplacement/empreintes et état de publication distinct ; aucune sauvegarde locale appelée enregistrement métier. |
| R56 | Intention de la proposition | Lecture client seul : compréhension de l’expérience, transformation, mission de l’agence et décision, soutenue par les pages. |
| R57 | Exports et contexte autonomes | PDF lisibles, structure PPTX vérifiée élément par élément, créations visuelles comme images indépendantes, contexte compilé et actifs ouvrables ; essai d'édition/réexport avec outil et portée déclarés. Un contrôle requis absent reste non validé. |
| R58 | Compteurs hors client | Inspection des pages, métadonnées, commentaires et paquet client : aucune télémétrie opérationnelle ou note d’exécution interne. |
| R59 | Défauts non compensés | Chaque obligation et chaque réviseur conserve son verdict ; aucun oubli, fuite ou inconnu décisif masqué par une moyenne. |
| R60 | Correction et recontrôle | Défaut→cause→modification localisée→dépendants invalidés→preuve nouvelle ; pas de PASS hérité d’un export précédent. |
| R61 | Méthodes adaptées au cas | Choix de techniques justifié par secteur, publics, objectif et complexité ; aucun effet, mouvement ou style imposé universellement. |
| R62 | Pas de contamination client | Contrôle texte/visuels/métadonnées/contacts des sorties exactes contre l’identité courante ; aucun reste d’un autre projet. |
| R63 | Communication utile | Messages d’avancement brefs : état vérifié, décision, limite et prochain travail ; détails opérationnels dans reçus, pas le client. |
| R64 | Usage authentifié dédoublonné | Si instrumentation privée exposée : reçu d’acteur authentifié et clé de déduplication sans contenu privé ; sinon capacité/mesure indisponible déclarée, jamais succès simulé. |
| R65 | Version et portée de remise | Manifeste daté/versionné, destinataire par rôle et statut candidat/validé, limites et droits ; aucune autorisation de production implicite. |
| R66 | Intégration additive | Diff/installation borné au périmètre déclaré ; aucune modification du connecteur privé ni configuration globale non autorisée. |
| R67 | Chargement progressif | Reçus de rôles et références ciblés, paquet commun borné et empreintes ; pas de transfert systématique d’historique privé ou corpus entier. |
| R68 | Idée prolongée | Visions et moments au-delà de la couverture prolongent le même concept avec fonctions distinctes ; pas de répétition décorative. |
| R69 | Canaux pertinents | Graphe des réseaux/médias/documents avec preuve d’association, confiance d’identité, tentative, accès et lacunes. |
| R70 | Bon sujet photographique | Chaque crédit et actif vérifié contre l’entreprise, produit, lieu ou personne réellement représentés ; homonyme et stock distingués. |
| R71 | Originaux et retouches | Original conservé, instructions/transformations fidèles et version dérivée reliés ; preuve que la retouche ne modifie pas un fait produit. |
| R72 | Synthétique correctement classé | Scène factuellement inventée classée synthétique indépendamment du ratio texte/visuel ; mesure photographique séparée par livrable. |
| R73 | Direction non interchangeable | Revue comparative des choix liés au client ; défaut d’idée propre signalé même si l’exécution paraît soignée. |
| R74 | Phrases autonomes | Lecture de chaque affirmation utile sans historique oral ; objet, action, bénéfice et limites se comprennent sans reformulation de l’auteur. |
| R75 | Voix préservée | Comparaison à des échantillons client sourcés ; jargon et abstractions interchangeables corrigés sans effacer les choix de voix. |
| R76 | But et comportement distincts | Intentions annoncées conditionnelles ; interaction réelle déclarée seulement après preuve d’état, action et résultat sur source construite. |
| R77 | Certitude technique | Matrice CMS/stack/agence/booking avec source/date/statut/confiance et contrôle restant ; fournisseur probable non confirmé. |
| R78 | Brief de rôle autonome | Paquet public en liste blanche avec enjeu, idée, mission, preuves, limites et fichiers/empreintes ; lecteur sans historique peut reprendre. |
| R79 | Trois statuts indépendants | Reçu sépare qualité des fichiers, droit de remise/diffusion et persistance/readback ; aucun statut déduit d’un autre. |
| R80 | Essai et attribution bornés | Protocole, entrées, modèle/capacités, variantes et sorties réelles conservés ; limites et contrôles réussis rapportés sans causalité exagérée. |
| R81 | DA neuve pour l’entreprise | Choix d’univers justifiés depuis preuves et idée client ; comparaison montre qu’aucune palette, typographie ou composition maison n’est imposée. |

Les obligations conditionnelles sont exclues seulement sur condition observable documentée. Les capacités indisponibles restent distinctes d’un contrôle exécuté et de son résultat. Aucune preuve périmée, score moyen ou déclaration de l’auteur ne clôt une obligation active sans son observation requise.
