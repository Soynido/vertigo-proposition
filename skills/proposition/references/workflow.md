# Routage du travail

Une URL ouvre la recherche, pas une demande obligatoire de brief. Le brief est une sortie de la compréhension. Le projet reste candidat tant que les capacités et fichiers annoncés ne sont pas prouvés.

| Passage stable | Sortie utile | Compétence ciblée si disponible |
|---|---|---|
| preflight | Doctor, dépendances et états de capacité | proposition |
| discovery.site | Menus/sous-menus et états desktop/mobile, sources, captures et issues de chaque destination | proposition-discovery |
| discovery.channels | Réseaux, documents, médias et essai historique Wayback borné après identification actuelle | proposition-discovery |
| company.v1 | Offre, publics, voix, preuves, parcours et outils ; observation/déclaration/hypothèse/inconnu | proposition-discovery |
| analysis.specialists | SEO/GEO, UX, design et marché utiles à la décision, reliés aux preuves | proposition-strategy |
| company.v2 | Contradictions réconciliées et questions ciblées encore ouvertes | proposition-strategy |
| brief.public | Sources analysées, observations, changements recommandés, objectifs, codes à préserver, idée, démonstration, mission et décision ; projection autorisée hachée | proposition-strategy |
| creative.direction | Mondes candidats sourcés ; scène centrale inspectée par monde ; comparaison puis sélection ; progression web et mobile des directions retenues | proposition-creative + proposition-story |
| client.composition | Récit depuis les preuves ; carte éditoriale, scènes utiles et mission concrète ; source HTML/CSS et médias locaux | proposition-composition |
| review.client | Revues distinctes sur la même révision et défauts localisés | proposition-quality |
| internal.handoffs | Playbook de vente de la mission d'agence ; transmission de sa réalisation | proposition-sales + proposition-technical |
| export.documents | Trois PDF, PowerPoint client à structure modifiable, contexte compilé, sources, médias utiles, email local et manifeste | proposition-composition |
| verify.final | Toutes les pages et diapositives exactes, édition PPTX, contexte autonome, liens, contenus, géométrie, séparation et empreintes | proposition-quality |
| publication.approved | Plan exact, accord lié au hash, effet puis readback | Adaptateur autorisé |

Les phases peuvent se chevaucher si leurs entrées sont valides ; un travail conditionnel porte ses hypothèses. Les recommandations de parcours définitives attendent les issues de tous les menus et sous-menus recensés. Une destination inaccessible compte comme tentative documentée, jamais comme analyse réussie. Les analyses approfondies par famille peuvent être échantillonnées avec périmètre explicite.

La passation reste sources → analyse → observations/recommandations → brief → création. Préparer les médias en parallèle n'autorise pas à présenter une création libre comme la réponse à une analyse encore absente. Le contrat créatif consomme le brief ; il ne remplace pas la recherche. Une exploration seule reste un candidat de portée créative, sans verdict de parcours complet.

L'exploration précède la sélection : pour un nouveau prospect, rendre au moins deux mondes centraux distincts avant de choisir. La même opportunité peut recevoir plusieurs réponses créatives ; une nouvelle tâche n'est pas exigée. Le mandat par défaut autorise le choix motivé après comparaison. Une instruction externe de nombre ou de direction déjà choisie garde sa preuve ; elle ne se déduit pas du brief auto-rédigé. Développer ensuite les seuls mondes retenus jusqu'à leurs trois moments et mobile. Figer ces scènes avant montage selon [le contrôle de préservation](../../proposition-composition/references/preservation.md). La présence et la fidélité dans les PDF/PPTX exacts bloquent les gates de composition/export et le verdict global. Les candidats écartés restent archivés dans les preuves, sans imposer un catalogue de pistes au client.

Un seul propriétaire compose la source canonique selon [le contrat de montage](../../proposition-story/references/argument.md) : la carte des pages suit l’argument, pas l’inventaire des scènes. Les états du site ne sont pas des pages imposées du deck ; les compléments retenus restent préservés en annexes lisibles. La portée client seule limite les fichiers remis, pas la prestation à vendre.

La correction suit le défaut : wording local → édition ; idée faible → brief ; incohérence de DA → direction ; source modifiée → invalidation des dépendants. Une boucle sans amélioration conserve un checkpoint et explique le blocage. Elle ne baisse pas le seuil.

Références de méthode : [collecte et récit modulaires](https://github.com/ilexlyu/ad-proposal-skills), [contexte marketing](https://github.com/coreyhaines31/marketingskills/tree/main/skills/product-marketing). Les versions réellement chargées sont celles du reçu upstream, pas implicitement ces branches mobiles.

Avant chaque passage, utiliser `next-stage RUN_DIR`. Le [contrat de preuves de progression](experience-evidence.md) relie brief, quatre méthodes réellement transmises, scènes rendues, actions conservées et carte client aux gates existants. Aucun pipeline parallèle : une faiblesse locale revient au passage responsable. En mode client seul, les dossiers internes sont exclus explicitement, jamais marqués comme réalisés.

En reprise, préparer seulement les fichiers nécessaires avec `prepare-inputs` selon [la CLI](cli.md). Entrée indisponible : checkpoint rapide, pas d’attente silencieuse ni de nouveau crawl. Exporter une révision neuve ; les finalizers PPTX de l’hôte conservent leurs reçus au lieu de les supprimer pour contourner une collision.
