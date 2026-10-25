# Note à chaque étape et preuve à chaque case

Chaque étape rend son rapport propre, en plus des revues de direction/client/interne. Lire les cinq critères canoniques du passage dans le registre embarqué `scripts/proposition_runtime/data/stages.json`. Les champs et identifiants de la version installée font autorité ; ne pas inventer une autre clé de contrat.

Pour chacun des cinq critères : note, observation localisée, preuve et empreinte, défaut et correction. Ancrages : **0** = résultat absent, trompeur ou inutilisable ; **1** = résultat présent mais partiel, source/contrôle décisif manquant ; **2** = résultat spécifique au passage, soutenu par ses preuves et utilisable par le suivant. La complétude intégrale décrite ci-dessous est ce qui justifie 2, pas l’existence d’un titre.

| Étape | Cinq objets de jugement observables |
|---|---|
| discovery.site | Menus/sous-menus desktop réellement ouverts ; mobile réellement ouvert ; destinations avec issues documentées ; états révélés rendus/capturés ; profondeur et limites de couverture explicites. |
| discovery.channels | Association des canaux à la bonne entité ; sources et dates précises ; tentatives/limites d’accès documentées ; médias reliés à leur vrai sujet ; provenance et droits distingués. |
| company.v1 | Offre/publics extraits des sources ; faits typés et traçables ; apports fournis conservés ; contraintes/capacités/responsable non inventés ; modèle exploitable avec inconnues visibles. |
| analysis.specialists | Questions utiles à la décision ; preuves et portée des constats ; comparables choisis par rôle ; méthodes/capacités réellement reçues ; implications propres au cas et limites. |
| company.v2 | Contradictions explicites ; arbitrages sourcés ou conditionnels ; manque actif et effet sur la décision ; dépendants mis à jour ; modèle cohérent utilisable pour le brief. |
| brief.public | Enjeu/public/changement intelligibles depuis observations et recommandations ; idée et démonstration ; mission d’agence et décision ; preuve/contre-hypothèse/inconnu ; projection autorisée autonome et hachée. |
| creative.direction | Mondes distincts rendus et comparés avant sélection, selon mandat externe vérifié ou exploration par défaut ; spécificité et signes client ; provenance photographique ; système et progression des seuls mondes retenus ; vérité des médias. Le registre embarqué fournit les cinq identifiants exacts. |
| client.composition | Histoire preuve → changement visible → bénéfice → mission → décision ; mots concrets ; équilibre utile mesuré ; desktop/mobile lisibles dans le deck ; séparation client. |
| review.client | Contextes réellement isolés ; entrées identiques et empreintes ; obligations et qualité séparées ; observations/défauts localisés ; correction et décision sans moyenne entre réviseurs. |
| internal.handoffs | Fidélité au projet final ; vente de la mission d’agence et actions suivables ; technique avec critères de reprise ; preuves/dépendances/certitudes ; séparation et limites privées. |
| export.documents | Révision source commune ; trois projections réelles plus PPTX client et contexte compilé ; impression/ressources fidèles ; sources et actifs autonomes ; manifeste et empreintes exacts. |
| verify.final | Toutes les pages et diapositives exactes lues ; mots/affirmations/liens contrôlés ; géométrie, médias et édition structurelle contrôlés ; confidentialité, identité et contexte vérifiés ; reçus/empreintes frais et limites. |
| publication.approved | Plan exact et destinations ; accord acteur/hash courant ; connecteur et portée autorisés ; déduplication/incertitude maîtrisées ; effet relu avec états séparés. |

Le seuil de chaque étape est 9/10 sans défaut bloquant, avec toutes ses obligations obligatoires applicables prouvées. Pas de moyenne entre étapes ou réviseurs. Une case Rxx non prouvée bloque même si le rapport d’étape obtient une bonne note. Les [81 preuves minimales](acceptance.md) rendent le contrôle par case explicite.

Une étape non exécutée est `NOT_RUN`, une capacité indispensable absente `BLOCKED`, une observation qui échoue `FAIL`, une validation invalidée par modification `STALE`. `NOT_APPLICABLE` demande une condition et une justification de portée, pas un moyen de contourner une case difficile.

Le barème reste **candidat sans calibration humaine**. Un jugement par agent peut être utile et reproductible dans son protocole ; il n’est pas le retour d’une personne réelle ni une qualité garantie.

## Progression créative et critères non compensables

Appliquer [les preuves de progression](experience-evidence.md) et les critères `required_full_scores` du registre : ils exigent chacun 2/2. Un total de 9 ne compense pas un système créatif partiel ou une faiblesse majeure de démonstration, langage ou spécificité. Le contrôle des fichiers ne mesure pas l’émotion : inspecter les scènes, leur rythme et le moment singulier. Une belle couverture seule ne qualifie pas une direction. Les mesures déclarées de lisibilité doivent être confrontées aux styles et aux images réelles.

Le mode `parameters.delivery_scope: client` exclut les dossiers internes de la validation applicable ; il ne dispense d’aucune analyse ni revue client. `next-stage` utilise les enregistrements du run, pas les notes annexes. Aucun plafond implicite de pages ; seule une limite explicite s’applique.

Les ancrages précis de `creative.direction.system` et `review.client.visual` du registre exigent des zones de vraies interfaces et une comparaison artistique située. Conformité mécanique, force commerciale et appréciation artistique restent distinctes ; un total élevé ne compense pas un critère critique partiel.
