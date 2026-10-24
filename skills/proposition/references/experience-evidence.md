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
| `direction_ids` | IDs uniques des directions demandées ou encore ouvertes. |
| `methods` | Une entrée par famille exacte `claude-seo`, `impeccable`, `apple-design`, `scroll-craft`. Chacune : `{family, commit, reference_ref, reference_root}`. |
| `observations` | Entrées `{id, proof, decision, reason, benefit}`. `decision` vaut `retained` ou `excluded`. Une retenue a son bénéfice envisagé ; une exclusion sa raison. |
| `actions` | Entrées `{id, proof, target, label}` pour les actions importantes existantes, y compris les chemins rapides. Inventaire établi avant création, sans suppression rétrospective. |

`proof` référence une vraie `source:ID` ou `fact:ID` enregistrée, avec bytes courants. Ne pas inventer un défaut pour atteindre un quota d’opportunités.

Pour les méthodes : `commit` vient du verrou installé ; `reference_ref` pointe un artefact Markdown copié depuis l’entrypoint primaire de la famille ; `reference_root` indique son arbre public complet vérifié dans le cache. `upstream status` fournit les chemins et l’état ; utiliser `upstream fetch` si nécessaire, sans exécuter de script/installateur. Enregistrer la source publique (URL de commit, copie locale), puis l’artefact avec provenance. Le moteur vérifie la concordance d’octets de l’entrypoint et réutilise le contrôle du cache complet : reçu, inventaire et fichiers doivent correspondre au verrou. Ce contrôle d’intégrité local ne prouve pas qu’une méthode a été lue ou exécutée.

Le créatif reçoit le paquet public **et l’accès explicite à ces arbres publics**, sans autre client ni historique privé. Il lit progressivement les fichiers pertinents, y compris les références liées par les SKILL. L’allowlist de `context-packet` inclut brief, `creative-inputs` et les quatre artefacts de méthodes, approuvés localement pour cette projection et avec provenance. La commande refuse une passation amputée de ces références. Les chemins de travail ne sont jamais recopiés dans le document client.

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

`action_text_px` est une mesure déclarée à étayer par capture et styles observés à la largeur mobile cible. La revue la vérifie. Le moteur bloque sous le plancher interne de 14 px ; il ne mesure pas la police depuis un PNG et ne certifie pas WCAG.

Une cible d’action reste celle de l’inventaire. Un changement autorisé emploie `disposition: changed_with_approval`, `reason` et `approval_ref` vers un JSON `{action_id, from, to, decision:"approved", actor, authority_proof}`. La dernière référence pointe la vraie instruction autorisant le changement. Ne pas fabriquer cette approbation. Le contrôle lie les pièces déclarées, sans authentifier une personne.

Ce gate qualifie des intentions statiques uniquement. Un comportement développé exige une qualification de prototype séparée, sans renommage opportuniste de `motion_status`.

## Montage : artefact `client-story`

Enregistrer `client-story.json` avec l’ID `client-story` :

- `pages` : entrées `{role, page, message, proof}`. Rôles requis : `understanding`, `evidence`, `opportunity`, `creative_world`, `transformation`, `agency_value`, `mission`, `next_step`. Fonctions éditoriales, pas huit pages obligatoires : plusieurs peuvent partager une page. Chaque page existe dans le PDF courant enregistré `client-pdf`.
- `observation_decisions` : `{id, page, reason}` pour chaque observation des inputs. Une retenue a une page réelle ; une exclusion conserve sa raison. Corriger sélection ou montage si la donnée existe, plutôt que relancer un crawl.
- `next_step` : `{decision, followup}` intelligibles et concrets. Responsable, adresse et modalité ne sont jamais inventés ; un manque décisif demeure visible dans le contrôle.

Le JSON vérifie les liens ; la carte éditoriale `client-story-map` suit [le contrat de montage](../../proposition-story/references/argument.md) et démontre sur les pages exactes la chaîne preuve → changement visible → bénéfice envisagé → mission → décision. Les scènes du site ne dictent pas le plan du deck. Les variantes restent identifiées ; les compléments conservés vont en annexe à la taille requise par le verrou, pas en simples miniatures.

L’univers peut se montrer par moodboard, matières ou scènes développées. La valeur d’agence explique pourquoi le changement justifie Vertigo ; la mission ne dit pas seulement « faire un beau site ». Le prochain échange indique comment poursuivre.

Conserver le rapport `client-copy-review`, avec méthode Stop Slop réellement lue et relecture du sens en français : action/objet, conséquence, preuve/condition. Garder le relevé de surfaces, la comparaison PDF/PPTX et l’essai d’édition dans leurs preuves existantes. Une fonction déclarée dans ce JSON ne prouve pas sa qualité dans la slide.

## Contrôles et portée

```text
python3 <MAIN_SKILL_DIR>/scripts/proposition.py check-experience RUN_DIR
python3 <MAIN_SKILL_DIR>/scripts/proposition.py check-creatives RUN_DIR
python3 <MAIN_SKILL_DIR>/scripts/proposition.py stage-report RUN_DIR creative.direction
python3 <MAIN_SKILL_DIR>/scripts/proposition.py stage-report RUN_DIR client.composition
python3 <MAIN_SKILL_DIR>/scripts/proposition.py validate RUN_DIR
```

Le contrôle d’expérience bloque direction, composition, export et vérification finale si les preuves manquent ou divergent. Figer tous les `creative_id` retenus, moments et mobiles compris, avec leurs empreintes : la préservation les retrouve ensuite dans les exports exacts. Une révision modifiée demande reprise explicite et invalidation des dépendants.

PASS signifie cohérence de pièces, pas beauté, phrases justes, mesures déclarées véridiques ou satisfaction client. Les deux revues isolées et les critères visuels renforcés ne peuvent pas être remplacés par ces JSON. Une référence non lue ou un constat inventé reste faux même si le fichier est bien formé.
