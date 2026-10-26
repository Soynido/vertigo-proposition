# Navigation observée et gate Discovery

Le collecteur est borné ; `captured` ne qualifie que les pages/états explicitement vérifiés. Le rapport courant est en version `2.0`. Les anciens rapports `1.0` restent des sources consultables mais ne peuvent certifier rétroactivement le nouveau contrôle.

## Exécution canonique

1. Le run existe déjà. `doctor`, collecte et export résolvent le même navigateur. Sans canal explicite, Chrome puis Chromium ; un canal explicitement indisponible bloque au lieu de se substituer silencieusement.
2. `collect URL --output RUN_DIR/research/LOT --max-pages N`. Le rapport et ses preuves restent dans le run, hors checkout. Aucun écrasement. Le code CLI non nul d'un lot partiel signale une limite ; lire le JSON, conserver les preuves, puis traiter les manques.
3. `discovery register RUN_DIR --report RUN_DIR/research/LOT/discovery.json`. L'enregistrement lie sources, captures, interactions, couverture et hashes au gate existant. Ce reçu n'attribue aucune note de qualité.
4. `collect --frontier RAPPORT --output RUN_DIR/research/LOT-SUIVANT --max-pages N` puis enregistrer ce lot. La filiation doit continuer une preuve enregistrée ; ne pas relancer un ancien rapport altéré. Une URL vue n'efface pas un état mobile manquant. Une reprise au plus de l'état échoué ; ensuite complément hôte ou checkpoint.
5. `discovery check RUN_DIR`, puis évaluation R08/R09/R10 et revue isolée des captures exactes. Leurs preuves incluent `artifact:site-discovery`. `stage-report`, `next-stage` et `validate` consomment ce contrôle ; une note de 9/10 ne le contourne pas.

## États effectivement observés

Bandeaux HTML : attendre de manière bornée, fermer/refuser les options facultatives par un contrôle visible et vérifier l'état après action. Ne pas cacher l'obstacle par CSS, le retirer du DOM depuis un script, ou forcer le clic. Conserver la capture avant et après ; impossible à fermer = manque explicite.

Menus : ouvertures, sous-menus, puis fermetures enregistrés. Défilement : captures avec recouvrement, positions, hauteur/viewport, stabilisation et images visibles réellement chargées ; panneaux internes pertinents aussi. Arrêt au plafond, contenu instable ou capture manquante = `partial` avec obligations restantes. Une fin de document ne prouve pas à elle seule la compréhension des contenus.

## Contrat du rapport et complément hôte

Les commandes du collecteur produisent le format canonique. Un complément du navigateur connecté de l'hôte doit produire les **mêmes observations**, pas recopier un statut PASS :

- `schema_version: "2.0"`, `batch_id` neuf, `input_url` du run, dates ISO avec fuseau, statut et limites ; backend/outils réellement utilisés déclarés.
- `pages` : URL demandée/finale, viewport `desktop|mobile`, statut, preuves, interactions et `exploration` avec manques et géométrie du scroll. Une preuve référence sa source, texte/HTML et capture locale ; positions/hauteurs et images visibles viennent de l'état observé.
- `sources` : identifiants uniques, URL/viewport/date, artefacts relatifs avec SHA256 et taille ; les preuves d'une page doivent correspondre à sa source et au viewport. Les images doivent être lisibles. Aucun chemin hors du dossier ou lien symbolique.
- `coverage` : destinations découvertes/tentées, frontière et états restant à traiter. Les lots sont conservés ensemble ; un lot ultérieur complète les seuls états manquants. `continuation.previous_report_sha256` lie au rapport enregistré précédent ; les sources/dates ne sont pas réutilisées comme une visite neuve.
- `link_entries`, candidats sociaux/médias et restrictions conservés. Le gate ne déduit ni analyse sémantique ni qualité visuelle de ces champs.

Consulter l'exemple de rapport réellement produit par la commande avant de préparer un complément. Les ressources hors origine ou documents embarqués bloqués par le collecteur ne démontrent pas un défaut du site. Employer le navigateur hôte autorisé pour observer réellement les états manquants ; conserver ses captures et textes, sa provenance, la limite et la révision. Sans complément possible, checkpoint : aucune déclaration de complétude inventée.

Le collecteur strict ne suit pas implicitement une redirection vers un autre hôte, y compris `www`. Pour un complément hôte qui a réellement observé la redirection HTTPS vers la variante `www` du domaine initial, déclarer `backend: "host-browser"` et la chaîne `pages[].redirects` (`from`, `to`, `http_status`). Le rapport conserve l'URL initiale et les URL finales/captures. Ce rapprochement de preuves ne change pas la politique réseau du collecteur ; un domaine tiers n'est pas accepté comme le prospect. Un autre domaine régional ou une identité ambiguë demande une qualification distincte.

## Tentatives externes et registre commun

Après consultation des canaux/documents autorisés, enregistrer leurs sources dans le run, puis écrire un journal JSON local : `version: 1`, `attempts` contenant `url`, `status`, `observed_at`, `source_id` (identifiant enregistré ou null), `reason` si inaccessible/exclu. Statuts : `retrieved`, `unavailable`, `document_not_analyzed`, `excluded`. Les deux premiers statuts de récupération (`retrieved`, `document_not_analyzed`) demandent une source collectée avec cette URL comme locator ; le journal seul ne prouve pas le contenu récupéré.

`discovery reconcile RUN_DIR --report JOURNAL` puis `discovery channels RUN_DIR` rapprochent chaque entrée et les candidats sociaux structurés de leur tentative. Une source peut servir plusieurs entrées sans les fusionner. Inaccessible/exclu exige une raison. La consultation reste distincte de l'officialité, de l'analyse et des droits ; les gates canaux et l'inspection humaine conservent ces obligations. Un nouveau journal est une nouvelle preuve immuable. `source_id` est l'identifiant enregistré sans préfixe `source:`.

Dès qu'un journal externe est enregistré, relier les évaluations et la revue de `discovery.channels` à `artifact:discovery-channels`, le bundle courant. Un nouveau journal change ce bundle et périme les jugements dépendants ; la revue de l'ancien journal ne valide pas les nouvelles preuves. Le gate recoupe les entrées observées avec l'inventaire déclaré : une destination interne omise de `coverage` ne disparaît pas des obligations. Une image déclarée visible mais non chargée reste une contradiction de complétude.
