# Preuves d’expérience et histoire client

Ce format est consommé par le moteur ; il ne constitue pas une deuxième procédure créative. Ces fichiers restent des preuves de travail locales, jamais des notes techniques cachées du deck.

## Périmètre et progression

Profil : `parameters.delivery_scope` vaut `full` par défaut ou `client` pour PDF/PPTX client seuls. Aucune limite de pages implicite. Pour une limite demandée explicitement, transmettre `--max-pages N` à l’inspection du PDF et consigner ce périmètre dans le reçu de revue.

Avant de changer d’étape :

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py next-stage RUN_DIR
```

La commande indique la première étape active non passée et ses manques ; elle ne crée ni note, source, collecte ou revue. Enregistrer réellement sources/faits/artefacts, évaluations Rxx et revues d’étape avec reçus. Un fichier `stage-notes.json` ou un message « 10/10 » ne remplace pas ces registres. En mode client, `internal.handoffs` est exclu de la qualité demandée ; toutes les étapes client et les deux revues requises restent nécessaires. La publication est séparée.

Un candidat autorisé peut avancer sous hypothèses explicites ; il n’est jamais présenté comme promu tant que les gates actifs ne passent pas. Une note 8/10 appelle une correction ciblée ou un checkpoint, pas une compensation par l’export final. Ne pas relancer les étapes valides.

## Entrée : artefact `creative-inputs`

Enregistrer un JSON avec l’ID `creative-inputs` :

| Champ | Contenu obligatoire |
|---|---|
| `revision` | Version stable du brief. |
| `direction_ids` | IDs uniques des mondes candidats avant création. Sur les nouveaux runs, le défaut exige au moins deux candidats ; les IDs développés sont ensuite le sous-ensemble retenu par la comparaison. |
| `methods` | Une entrée par famille exacte `claude-seo`, `impeccable`, `apple-design`, `scroll-craft`. Chacune : `{family, commit, reference_ref, reference_root}`. |
| `observations` | Entrées `{id, proof, decision, reason, benefit}`. `decision` vaut `retained` ou `excluded`. Une retenue a son bénéfice envisagé ; une exclusion sa raison. |
| `actions` | Entrées `{id, proof, target, label}` pour les actions importantes existantes, y compris les chemins rapides. Inventaire établi avant création, sans suppression rétrospective. |
| `opportunity` | Nouveaux runs contrat 2 : `{audience, task, proof, change, benefit, scope, alternative, brand_codes:{preserve:[], adapt:[], unknown:[]}}`. Une opportunité principale et un périmètre justifié ; l’esthétique ne démontre pas seule la nécessité de refonte. |

`proof` référence une vraie `source:ID` ou `fact:ID` enregistrée, avec bytes courants. Ne pas inventer un défaut pour atteindre un quota d’opportunités.

Pour les méthodes : `commit` vient du verrou installé ; `reference_ref` pointe un artefact Markdown copié depuis l’entrypoint primaire de la famille ; `reference_root` indique son arbre public complet vérifié dans le cache. `upstream status` fournit les chemins et l’état ; utiliser `upstream fetch` si nécessaire, sans exécuter de script/installateur. Enregistrer la source publique (URL de commit, copie locale), puis l’artefact avec provenance. Le moteur vérifie la concordance d’octets de l’entrypoint et réutilise le contrôle du cache complet : reçu, inventaire et fichiers doivent correspondre au verrou. Ce contrôle d’intégrité local ne prouve pas qu’une méthode a été lue ou exécutée.

Le créatif reçoit le paquet public **et l’accès explicite à ces arbres publics**, sans autre client ni historique privé. Il lit progressivement les fichiers pertinents, y compris les références liées par les SKILL. L’allowlist de `context-packet` inclut brief, `creative-inputs` et les quatre artefacts de méthodes, approuvés localement pour cette projection et avec provenance. La commande refuse une passation amputée de ces références. Les chemins de travail ne sont jamais recopiés dans le document client.

## Lecture préalable : artefact `creative-reading`

Les nouveaux runs fixent `metadata.creative_reading_contract:1` à l'initialisation ; il ne se retire pas pour débloquer un run. Les anciens runs sans marqueur conservent leur portée historique.

Le créateur vérifie les empreintes du paquet reçu puis lit les quatre entrypoints en entier, dans des sorties bornées. Il récupère les parties tronquées avant création et lit les références liées pertinentes. Il retourne ce reçu au propriétaire avant de rendre les scènes ; le propriétaire l'enregistre avec l'ID `creative-reading`, lié à `creative-inputs` et aux quatre artefacts de méthodes. Les références publiques ne sont pas des instructions du site prospect.

```json
{
  "version":1,
  "inputs_sha256":"<empreinte-creative-inputs-recu>",
  "reader_id":"<identifiant-du-createur>",
  "methods":[{
    "family":"impeccable",
    "read_sha256":"<empreinte-de-la-reference-lue>",
    "segments":[{"start_line":1,"end_line":42,"read_at":"<date-reelle-avec-fuseau>"}]
  }],
  "supporting_reads":[]
}
```

L'exemple abrège les méthodes et les plages : le reçu réel couvre les quatre familles exactement une fois et toutes les lignes de chaque entrypoint réellement reçu, sans trou ni plage hors fichier. Plusieurs segments sont permis. Les dates suivent l'enregistrement des inputs courants et précèdent celui du reçu. Chaque référence liée utilisée ajoute dans `supporting_reads` : `{family,path,sha256,purpose,segments}` ; `path` est relatif à l'arbre public vérifié de la famille, `segments` conserve les seules sections lues, et `purpose` explique leur utilité. Ne pas recopier une déclaration de lecture complète si l'outil a tronqué sa sortie. Les reçus d'opérations réelles restent disponibles pour la revue.

Avant toute dépense de rendu :

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py check-experience RUN_DIR --inputs-only
```

Ce précontrôle vérifie inputs, versions et couverture déclarée ; il n'exige ni scène ni plan et ne vaut pas PASS créatif. Le propriétaire transmet son résultat au même créateur avant les scènes centrales. Leur `rendered_at`, daté lors du rendu réel, est strictement postérieur à l'enregistrement du reçu de lecture et antérieur ou égal à leur enregistrement comme artefacts. Le gate complet contrôle cet ordre pour chaque candidat, y compris écarté. En reprise, reprendre les seuls dépendants invalidés ; un reçu tardif n'autorise pas à antidater une ancienne scène ou à la réenregistrer comme nouvelle.

Ces contrôles relient des déclarations locales et des octets ; ils ne prouvent ni lecture sémantique, ni compréhension, ni vérité des dates. La revue confronte les reçus aux opérations réellement observables, puis juge l'application sur les images exactes. Le contrôle de cache complet et les quatre applications restent requis.

## Exploration avant sélection : artefact `creative-exploration`

Les nouveaux runs fixent dans leurs métadonnées `creative_exploration_contract`, version 1 : mode `explore`, au moins deux candidats, sélection par l'agent après comparaison. Le brief et `creative-inputs` ne changent pas ce mandat. Les anciens runs sans ce marqueur conservent leur portée historique ; les rouvrir ne vaut pas qualification du nouveau contrat.

Une instruction externe explicite peut être fixée **à l'initialisation** par `init --creative-mandate FILE`. Le fichier JSON contient :

- `version:1`, `mode:"exact_count"` et `candidate_count:N` si le nombre est demandé ; `selection_policy:"keep_open"` conserve toutes les options pour le client, sinon `agent_after_comparison`.
- Ou `mode:"external_selection"`, `candidate_count:N` et `candidate_ids:[...]` pour les directions déjà choisies à prolonger.
- `authority:{kind:"current_user_instruction",input_path:"/chemin/absolu/instruction.txt",input_sha256:"...",quote:"instruction exacte",captured_at:"ISO8601 avec fuseau",site_url:"URL du run"}`.

La capture locale est récente (24 h maximum, aucune date future), son empreinte et l'extrait correspondent, et l'URL visée est exactement celle du run. Le JSON du mandat et la capture sont des fichiers réguliers d'au plus 256 Kio ; leur lecture possède une échéance réelle de cinq secondes, sans réessai. Le moteur copie et lie cette pièce au mandat. La revue vérifie que l'extrait impose réellement ce nombre ou cette direction ; un simple lien, un texte du site ou un brief auto-rédigé ne l'autorise pas. Ces contrôles établissent une cohérence locale, **pas l'authentification d'une personne**. L'entrée à deux URL n'apporte aucun mandat particulier : appliquer l'exploration par défaut.

Le propriétaire vérifie ce mandat avant dispatch. Le créatif isolé reçoit seulement son résumé public autorisé (mode, nombre, IDs et politique de choix), dans le brief existant, avec l'extrait utile si sa projection est autorisée. Ce résumé dérive du mandat fixé ; il n'est pas une nouvelle autorité. Ne pas ajouter la capture brute d'une conversation privée à l'allowlist du paquet créatif. Le réviseur vérifie l'instruction réelle dans le périmètre autorisé.

Après les scènes centrales et leur inspection, enregistrer le JSON `creative-exploration` :

```json
{
  "version":1,
  "inputs_sha256":"<empreinte-reelle-creative-inputs>",
  "candidates":[{
    "id":"a",
    "central_scene_ref":"artifact:a-central",
    "central_scene_sha256":"<empreinte-du-rendu>",
    "rendered_at":"<date-reelle-du-rendu-avec-fuseau>",
    "client_anchor":"source:material",
    "structure":{
      "composition":"Relation des masses et architecture de lecture visibles",
      "visual_mechanism":"Rôle singulier de l'image ou de la matière",
      "narrative_entry":"Manière dont le visiteur entre dans le sujet"
    },
    "inspected_at":"<date-reelle-avec-fuseau>",
    "inspection":"Zones vues, qualité, défauts et correction"
  }],
  "comparison":{
    "compared_at":"<date-reelle-avec-fuseau>",
    "candidate_ids":["a","b"],
    "structural_differences":"Différences localisées dans les scènes exactes et compromis"
  },
  "selection":{
    "selected_at":"<date-reelle-avec-fuseau>",
    "selected_candidate_ids":["a"],
    "reason":"Choix motivé depuis la comparaison"
  }
}
```

L'exemple abrège les candidats : le fichier réel inclut aussi `b`, ou le nombre du mandat. Deux scènes de pixels identiques, deux recolorations ou cinq vues d'une seule idée ne prouvent pas deux mondes. Le moteur vérifie rendus, empreintes, différences déclarées sur au moins deux dimensions, provenance et ordre daté ; la revue juge les différences effectivement visibles et leur intérêt.

Pour un mandat explicite à un seul candidat, conserver ce même reçu avec une scène centrale inspectée, `candidate_ids:["c"]` et `selected_candidate_ids:["c"]`. La comparaison consigne la vérification de la continuation et ses compromis, sans inventer de concours. C'est le mandat fixé qui autorise la cardinalité un ; cette forme de JSON seule ne l'autorise pas.

Ordre contrôlé : enregistrement de chaque scène centrale → inspection → comparaison → sélection → enregistrement de l'exploration → enregistrement du plan développé. Les nouvelles scènes de déclinaison suivent la sélection. Une scène centrale choisie peut être réutilisée comme un moment final. Le moteur ne prouve pas que les dates déclarées correspondent à une inspection humaine : conserver les opérations et leurs reçus réels.

Le propriétaire enregistre les rendus retournés par le créateur, puis les ouvre pour l'inspection et la comparaison retenues dans ce reçu. Une inspection antérieure du créateur peut rester dans ses notes ; elle ne devient pas une inspection rétrodatée après enregistrement. Il transmet ensuite au créateur la décision publique pour les prolongements, sans exposer l'état privé. En reprise, reprendre la même logique sur les seules preuves modifiées.

Les IDs de `creative-inputs` couvrent tous les candidats. Les directions de `creative-experience` correspondent exactement aux IDs sélectionnés. Les scènes centrales écartées restent dans les preuves et le contexte, sans obligation de les placer dans les exports client. Cette séparation préserve l'exploration et évite le catalogue de huit slides par défaut.

Chaque direction développée consomme sa scène centrale sélectionnée à l'empreinte comparée. Une correction de cette scène demande une nouvelle inspection/comparaison et une décision courantes, puis les seules validations dépendantes ; elle ne commande pas un nouveau crawl. Aucun ancien rendu n'est renommé pour simuler une création faite après sélection.

## Sortie : artefact `creative-experience`

Enregistrer un JSON avec l’ID `creative-experience`. Structure fictive à compléter avec des empreintes et preuves réelles :

```json
{
  "revision":"brief-r1",
  "inputs_sha256":"<empreinte-reelle-des-inputs>",
  "method_applications":[
    {"family":"impeccable","mode":"adapted","read_sha256":"<empreinte-reference-lue>","application":"Correction localisée de la hiérarchie et des actions","moment_ids":["a-reveal"]}
  ],
  "directions":[{
    "id":"a",
    "signature":{"moment_id":"reveal","client_anchor":"source:material","visible_change":"La matière révèle son usage à la bonne échelle"},
    "motion_status":"static_intent",
    "moments":[
      {"id":"opening","role":"opening","creative_id":"a-opening","render_ref":"artifact:a-opening","meaning":"Reconnaître le produit","proof":"source:material","scroll_position":0},
      {"id":"reveal","role":"reveal","creative_id":"a-reveal","render_ref":"artifact:a-reveal","meaning":"Comprendre son usage","proof":"source:material","scroll_position":0.5},
      {"id":"action","role":"action","creative_id":"a-action","render_ref":"artifact:a-action","meaning":"Accéder au devis existant","proof":"source:quote","scroll_position":1}
    ],
    "mobile":{"creative_id":"a-mobile","render_ref":"artifact:a-mobile","action_text_px":16,"action_id":"quote"},
    "actions":[{"id":"quote","target":"https://fixture.example/quote","moment_id":"action","label":"Demander un devis","disposition":"preserved"}]
  }]
}
```

L’exemple abrège les applications : le fichier réel nomme **les quatre familles** avec mode, empreinte et application à des `creative_id` rendus. `moment_ids` référence les `creative_id` des rendus (par exemple `a-reveal`), et non les IDs locaux des moments (`reveal`). `native` exige `execution_ref` vers un artefact JSON `{family, reference_sha256, status:"PASS", outputs:["artifact:ID"]}` avec sorties enregistrées et courantes ; ce reçu déclaré doit être confronté à l’exécution réelle. Sinon employer `adapted`. `unavailable` n’autorise pas une promotion ni un faux usage.

Chaque direction a au moins trois moments distincts en pixels et en sens, en progression, avec ouverture, révélation et action ; une signature sur une révélation liée à une source ; un mobile portrait distinct. Les positions de scroll décrivent l’intention statique, pas un comportement exécuté.

Les nouveaux runs fixent `parameters.proposal_contract: 2` à l’initialisation : opportunité requise ; le mobile ajoute `viewport_width_px` (largeur CSS cible) et `adaptation` (réorganisation concrète à inspecter). Ces déclarations ne prouvent ni responsive ni beauté. Les anciens profils sans ce paramètre gardent leur portée historique ; ne pas les réécrire pour reprendre un montage. Qualifier la scène maîtresse avant les déclinaisons, ou réutiliser une scène inspectée toujours valable.

`action_text_px` est une mesure déclarée à étayer par capture et styles observés à la largeur mobile cible. La revue la vérifie. Le moteur bloque sous le plancher interne de 14 px ; il ne mesure pas la police depuis un PNG et ne certifie pas WCAG.

Une cible d’action reste celle de l’inventaire. Un changement autorisé emploie `disposition: changed_with_approval`, `reason` et `approval_ref` vers un JSON `{action_id, from, to, decision:"approved", actor, authority_proof}`. La dernière référence pointe la vraie instruction autorisant le changement. Ne pas fabriquer cette approbation. Le contrôle lie les pièces déclarées, sans authentifier une personne.

Ce gate qualifie des intentions statiques uniquement. Un comportement développé exige une qualification de prototype séparée, sans renommage opportuniste de `motion_status`.

## Plan de composition préalable

Les nouveaux runs fixent `metadata.sales_kit_contract: 1` à l'initialisation ; cette version ne peut être retirée ou changée. Les runs historiques sans cette version conservent leur portée : ne pas les réécrire pour simuler une qualification du nouveau contrat.

Après exploration, sélection, développement et gel des scènes, `proposition-story` fournit la carte ; `proposition-composition` conçoit le deck. Son plan visuel situe l'ouverture et les raccords preuve→proposition puis proposition→mission→décision, avec rôle et échelle des scènes. Il peut être sommaire, regrouper les passages et réutiliser les mêmes médias. Le pilote à taille finale remplit le contrôle central existant, sans seconde exploration ni double reconstruction. Aucun outil de génération particulier n'est requis.

Enregistrer la carte JSON avec l'ID **`client-story-map`**. Ces champs sont requis ; le format de données n'impose ni nombre de slides ni forme graphique :

| Champ | Format / contenu |
|---|---|
| `version`, `revision` | `1`, puis nom de révision non vide. |
| `inputs_ref` | `artifact:creative-inputs`, déjà courant. |
| `creative_lock_sha256` | Empreinte réelle du verrou créé par `freeze-creatives`. |
| `coverage` | Huit entrées distinctes K01–K08 ; plusieurs peuvent partager une page. Chacune : `{id, page, anchor, message, proof, claim_status, visual_ref}`. Page entière positive, zone exacte, titre-conclusion et démonstration localisable. |
| `claim_status` par entrée | `observed`, `declared`, `proposed`, `estimate` ou `unknown`. |
| `proof` par entrée | `source:ID` publique observée ou `fact:ID` confirmé et explicitement autorisé publiquement. Ni assertion de l'auteur, ni source privée reclassée. |
| `visual_ref` par entrée | `artifact:ID` courant du paquet public/client du projet. |
| K03 : `mechanism` | Explication concrète du mécanisme montré dans les états ; voie publique du contrat de récit. |
| K06 : `effect`, `measurement` | Effet envisageable conditionnel ; `measurement.acquisition` et `.conversion`, chacun `{indicator, data_status, ...}`. `available` exige `proof` publique ; `unknown` ou `not_applicable` exige `reason`. Une mesure inconnue ne supprime pas K06. |
| K07 : `mission` | `{scope, included, excluded, conditions}` : périmètre concret, puis trois listes non vides de textes explicites. Raccordements non vérifiés conditionnés. |
| K08 : `decision` | Prochain accord concret ; aucun interlocuteur, prix ou calendrier inventé. |
| `visual_plan` | Trois entrées `{role, render_ref, inspection}` : `opening`, `proof_to_proposal`, `proposal_to_decision`. Le même rendu peut montrer plusieurs passages ; trois rôles ne signifient pas trois images/slides. |
| `pilot` | `{render_ref, intention_ref, comparison}` : rendu à taille finale et comparaison localisée avec un rendu du plan visuel. Rendus PNG/JPEG/WebP réellement enregistrés. |
| `outputs` | Chemins neufs des quatre sorties canoniques, comme ci-dessous. Le pilote utilise d'autres chemins. |

Extrait fictif pour les champs imbriqués ; le fichier réel contient les huit entrées complètes et leurs vrais sources/textes, pas ces phrases génériques :

```json
{
  "id": "K06", "page": 4, "anchor": "preuve-et-reponse",
  "message": "Conséquence précise du changement montré.",
  "proof": "source:observation", "claim_status": "proposed",
  "visual_ref": "artifact:scene-action",
  "effect": "Objectif conditionnel, distinct d'un résultat mesuré.",
  "measurement": {
    "acquisition": {"indicator":"Visites qualifiées","data_status":"unknown","reason":"Mesure privée indisponible."},
    "conversion": {"indicator":"Demandes utiles","data_status":"unknown","reason":"Mesure proposée après engagement."}
  }
}
```

```json
{
  "outputs": {
    "client-source": "client/r1/index.html",
    "presentation-catalog": "client/r1/presentation.json",
    "client-pdf": "client/r1/Proposition.pdf",
    "client-pptx": "client/r1/Proposition.pptx"
  }
}
```

Avant de fabriquer la source **complète**, son catalogue et ses exports, appeler :

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py check-experience RUN_DIR --composition-plan-only
```

Le mode enregistre **`composition-plan-review`**, ses entrées/empreintes et une date locale, sans PDF final. Les quatre chemins `outputs` doivent encore être inexistants. Il refuse un plan constitué après création des sorties, même non enregistrées. Relancer un préalable inchangé conserve le reçu d'origine. Une correction du plan ou de ses entrées périme le reçu et ses dépendants ; préparer des chemins de nouvelle révision, sans écraser les exports. La revue confronte la chronologie aux opérations réellement observées : un horodatage local ne constitue pas une attestation infalsifiable.

Après le préalable, enregistrer dans l'ordre **`client-source`**, **`presentation-catalog`**, **`client-pdf`**, **`client-pptx`**, puis **`client-story`**. Le moteur ajoute les dépendances disponibles vers plan/reçu/source ; déclarer aussi les CSS, actifs et sources consommés avec `--depends`. L'enregistrement générique d'une pièce intermédiaire ne donne pas PASS : le contrôle final refuse un paquet incomplet, antérieur ou non lié au préalable courant. Des champs complets ne prouvent ni le sens des images ni le WOW.

## Montage : artefact `client-story`

Enregistrer `client-story.json` avec l’ID `client-story` :

- `pages` : entrées `{role, page, message, proof}`. Rôles requis : `understanding`, `evidence`, `opportunity`, `creative_world`, `transformation`, `agency_value`, `mission`, `next_step`. Fonctions éditoriales, pas huit pages obligatoires : plusieurs peuvent partager une page. Chaque page existe dans le PDF courant enregistré `client-pdf`.
- `observation_decisions` : `{id, page, reason}` pour chaque observation des inputs. Une retenue a une page réelle ; une exclusion conserve sa raison. Corriger sélection ou montage si la donnée existe, plutôt que relancer un crawl.
- `next_step` : `{decision, followup}` intelligibles et concrets. Responsable, adresse et modalité ne sont jamais inventés ; un manque décisif demeure visible dans le contrôle.
- Pour les nouveaux runs : `kit_coverage` contient huit entrées `{id, page, anchor}` K01–K08, avec pages et zones **finales** du PDF/PPTX courants. Carte, reçu préalable, source et catalogue restent joints aux deux revues. Plusieurs fonctions peuvent partager une page. Le catalogue final n'est pas la preuve d'un plan antérieur.

Le JSON vérifie les liens ; la carte éditoriale `client-story-map` suit [le contrat de montage](../../proposition-story/references/argument.md) et démontre sur les pages exactes la chaîne preuve → changement visible → bénéfice envisagé → mission → décision. Les scènes du site ne dictent pas le plan du deck. Les variantes restent identifiées ; les compléments conservés vont en annexe à la taille requise par le verrou, pas en simples miniatures.

L’univers peut se montrer par moodboard, matières ou scènes développées. La valeur d’agence explique pourquoi le changement justifie Vertigo ; la mission ne dit pas seulement « faire un beau site ». Le prochain échange indique comment poursuivre.

Conserver le rapport `client-copy-review`, avec méthode Stop Slop réellement lue et relecture du sens en français : action/objet, conséquence, preuve/condition. Garder le relevé de surfaces, la comparaison PDF/PPTX et l’essai d’édition dans leurs preuves existantes. Une fonction déclarée dans ce JSON ne prouve pas sa qualité dans la slide.

En parcours complet, dériver `sales-playbook`, `follow-up-register`, `technical-handoff`, leurs sources/PDF et le contexte `client-context` depuis le client stabilisé. Ces IDs reçoivent les dépendances disponibles vers `client-source`, `presentation-catalog`, `client-pdf`, `client-pptx`, `client-story-map`, `client-story` et `composition-plan-review`. Paquet reçu et pages/ancres doivent correspondre ; réenregistrer une pièce préparée avant que ses entrées existent. Le gate des handoffs refuse les trois pièces de reprise sans cette chaîne. Une modification de mission/décision ou d'export périme les dérivés concernés. Le manifeste final inventorie les pièces sans devenir leur entrée. Aucune note privée dans le PPTX client.

## Contrôles et portée

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py check-experience RUN_DIR
python3 <MAIN_SKILL_DIR>/scripts/proposition.py check-creatives RUN_DIR
python3 <MAIN_SKILL_DIR>/scripts/proposition.py stage-report RUN_DIR creative.direction
python3 <MAIN_SKILL_DIR>/scripts/proposition.py stage-report RUN_DIR client.composition
python3 <MAIN_SKILL_DIR>/scripts/proposition.py validate RUN_DIR
```

Le contrôle d’expérience bloque direction, composition, export et vérification finale si les preuves manquent ou divergent. Figer tous les `creative_id` retenus, moments et mobiles compris, avec leurs empreintes : la préservation les retrouve ensuite dans les exports exacts. Une révision modifiée demande reprise explicite et invalidation des dépendants.

Sur les nouveaux runs, `freeze-creatives` vérifie aussi l'exploration, la sélection et les scènes développées **avant** d'écrire le verrou. Une note maximale ne contourne pas ce contrôle. Le critère créatif `options` exige 2/2 sur ces preuves, distinctement de `system`, qui juge la progression d'une direction retenue.

PASS signifie cohérence de pièces, pas beauté, phrases justes, mesures déclarées véridiques ou satisfaction client. Les deux revues isolées et les critères visuels renforcés ne peuvent pas être remplacés par ces JSON. Une référence non lue ou un constat inventé reste faux même si le fichier est bien formé.
