# Publics, besoins et passation stratégique

Ce contrat utilise les étapes existantes : `company.v1` reçoit faits et inconnus de Discovery ; `analysis.specialists` applique les deux méthodes et vérifie les missions utiles ; `company.v2` réconcilie ; `brief.public` transmet. Les missions ciblées ne relancent pas tout le crawl. Le créatif garde les quatre méthodes, l'exploration avant sélection et sa liberté de composition. Aucune nouvelle procédure de deck.

## Méthodes réellement accessibles

Dans le moteur installé, exécuter `strategy prepare RUN_DIR` (option `--cache CHEMIN` si cache partagé configuré). La commande vérifie/télécharge seulement les sources épinglées `marketingskills`, sans installer ses scripts, puis produit `native_task_path`. Lire ce fichier, les deux `SKILL.md` et les références utiles indiquées. Conserver les lectures et leur application dans le rapport ; l'existence du cache ne prouve pas une lecture.

Appliquer d'abord **product-marketing 2.2.0** à l'offre, différenciation déclarée, usages, publics et voix ; puis **customer-research 2.0.4**, modes sources existantes et signaux publics. Versions du lock, même commit `e85f3cbc2e4a79bf33b2a12e9bdd9087d414735b`. Les références et MIT sont distribuées avec ces sources. La référence entretiens reste disponible mais n'autorise aucun entretien ou questionnaire dans ce parcours.

Adapter les confirmations et accès privés demandés par défaut : brouillon public sourcé, aucune validation du propriétaire présumée, aucun CRM, analytics privé, contact ou donnée de revenus/prix à inventer. Un manque de confirmation n'empêche pas de décrire les éléments publics ; il interdit de les appeler positionnement validé. Lire `brand-voice.md` pour la voix et `source-guides.md` pour les sources de recherche. Les noms de plateformes ou snippets ne remplacent pas une lecture de leur contenu.

## Rapport dans `observation-analysis-map`

Créer un JSON `version: 1`, puis `strategy register RUN_DIR --report CHEMIN`. Ne pas réécrire les acquis pour remplir un format ; reprendre les constats actuels avec leurs preuves et conserver les décisions antérieures. Les collections ci-dessous portent des IDs uniques et stables, avec au plus 100 lignes chacune :

- `methods` : deux entrées `name` (`product-marketing`, `customer-research`), `commit`, `reference_root`, `sha256` du SKILL, `mode: adapted`, `read_sections` effectivement lues, `adaptation` publique précise et `applied_to` vers les IDs de publics/besoins concernés. Le cache complet sélectionné et ses empreintes doivent correspondre au lock. Garder les traces de lecture de l'hôte pour la revue ; les champs déclaratifs ne prouvent pas seuls la lecture.
- `audiences` : `id`, `role`, `kind` (`site_visitor` ou `vertigo_buyer`), `status` (`declared`, `attributed`, `hypothesis`), `source_ids`. Distinguer visiteur, personne citée, acheteur et prospect de Vertigo. Un rôle attribué à un témoignage n'est pas un segment validé ; aucun ICP prioritaire n'est déduit d'une fréquence non démontrée.
- `needs` : `id`, `audience_ids`, `status` (`observed`, `declared`, `hypothesis`, `unknown`), `source_ids`, `source_group`, `context`, `delta` (`new`, `corroboration`, `reformulation`, `baseline_not_compared`), `decision` (`retained`, `excluded`, `deferred`), `recommendation`, `alternative`, `mission_ids`. `source_group` identifie les bruts communs/republications pour éviter de compter deux fois une preuve. Préciser le passage/zone/date dans `context`. Hors `baseline_not_compared`, fournir `baseline_source_ids` vers l'état antérieur figé. Ajouter `experience_consequence` pour un besoin retenu ; sinon `reason` de non-retenue. Un besoin `unknown` ne peut pas justifier une opportunité retenue. Une hypothèse reste visible comme telle.
- `missions` : `id`, `need_ids`, `target` URL publique normalisée, `task`, `success`, `stop`, `outcome` (`completed` ou `blocked`), `source_ids` vers les traces, `limits` et `reason` si bloquée. Exécuter réellement la mission dans le navigateur : menu, scroll, contenu différé, retour et accès à l'action utiles. Réutiliser une preuve actuelle seulement si elle couvre exactement la tâche et ses états. Arrêter avant soumission/réservation/paiement. Une mission bloquée reste bloquée ; aucune préférence ou réussite utilisateur n'en est déduite.
- `unknowns` : liste des inconnus et de la décision qu'ils pourraient changer. Les détails internes sans effet sur l'expérience restent internes.

Tout besoin retenu rejoint au moins une mission, dans les deux sens. Une recommandation n'a pas besoin de refaire un site : comparer maintien, correction ciblée, landing ou refonte. Expliquer le contre-argument. Une observation de marché supplémentaire n'impose ni un nouveau concept ni une priorité commerciale. Si les sources ne permettent pas une synthèse utile, laisser l'étape bloquée avec le manque précis plutôt que fabriquer un profil.

## Conservation jusqu'au créatif

Le résumé `audience_need_summary` est le même dans les JSON existants `company-evidence-brief` et `creative-inputs` :

```json
{
  "audiences": [{"id":"a1","role":"Rôle sourcé","kind":"site_visitor","status":"hypothesis","source_ids":["public-source"]}],
  "needs": [{"id":"n1","audience_ids":["a1"],"status":"hypothesis","context":"Passage précis","delta":"baseline_not_compared","decision":"retained","recommendation":"Changement précis","experience_consequence":"Ce que le visiteur pourra découvrir ou faire","alternative":"Pourquoi l'existant pourrait suffire","source_group":"official-page"}],
  "unknowns": ["Priorité d'achat inconnue"]
}
```

Conserver tous les publics et besoins avec les champs montrés, y compris les décisions de non-retenue. Pour ces dernières, `experience_consequence` peut être vide ; leur justification reste dans le rapport interne. Le modèle dépend de `artifact:observation-analysis-map`, et `creative-inputs` dépend du modèle courant. Les observations créatives retenues portent `need_ids` et une preuve dont les dépendances conservent les sources du besoin. La conséquence fixe le problème ou l'action utile, sans imposer une mise en scène.

Contrôler `strategy check RUN_DIR --stage analysis.specialists`, puis `company.v2`, puis `brief.public` au moment de leurs gates existants. La commande ne note pas la qualité du positionnement. Les nouveaux runs vérifient conservation et dépendances dans ces gates ; les anciens restent lisibles dans leur portée. Le paquet public inclut déjà `creative-inputs` : son résumé doit donc rester public, sourcé et sans dossier privé. Les détails techniques et le rapport complet de recherche ne sont pas transmis automatiquement. La revue vérifie ensuite que besoin → preuve → recommandation → scène et action existent réellement ; aucune admission autonome depuis les seuls tests moteur.

## Reprise du rapport

Enregistrer à nouveau le même rapport au même chemin, avec les mêmes octets et dépendances, conserve sa date, ses empreintes et son approbation. Les modèles et briefs qui en dépendent restent valides. Une vraie modification du rapport ou de ses preuves continue de les invalider. Rejouer un rapport inchangé mais périmé ne le rend pas actuel : résoudre la cause et produire l'observation nécessaire avant de poursuivre.

Le contrat courant accepte uniquement l'entier `1`. Une clé présente avec un booléen, `null` ou une version inconnue est bloquante ; seule l'absence de la clé `audience_handoff_contract` dans les métadonnées désigne un ancien run sans ce contrat. Ces règles de reprise ne modifient ni le contenu exigé du rapport ni la conservation jusqu'au créatif.
