# Recherches publiques dans le registre existant

Après identification du site actuel, exécuter `discovery research-plan RUN_DIR`, lire son `native_task_path`, puis réaliser les opérations avec la recherche et le navigateur de l'hôte. La commande prépare la mission ; elle n'effectue aucune recherche. Réutiliser les sources actuelles et borner les reprises au manque utile.

| Topic | Opération et preuve attendue | Limite ou repli |
|---|---|---|
| `google_search` | Chercher entité, offre et pages pertinentes. Conserver requête, fournisseur réellement utilisé, résultats et pages lues. | Un moteur hôte n'est pas nécessairement Google. Aucun trafic privé ni positions exhaustives déduits. |
| `google_ads` | Consulter le Google Ads Transparency Center public pour annonceur/domaine confirmé ; noter pays, période et filtres. | Si bloqué, recherche publique ciblée, sans la présenter comme couverture de la bibliothèque. Aucun budget, ciblage ou rendement déduit. |
| `meta_ads` | Consulter la Meta Ad Library publique pour page/annonceur confirmé, pays et statut explicites. | Si bloqué, recherche publique ciblée avec sa portée plus faible. Aucun contournement de login/CAPTCHA. |
| `reviews` | Chercher et lire des avis publics indépendants sur l'entité confirmée ; échantillon utile avec dates et contexte. | Séparer témoignages sélectionnés par l'entreprise, republications et avis indépendants. Fonction citée ≠ acheteur ou ICP prioritaire. |

Un fournisseur spécialisé absent n'établit pas l'impossibilité des voies publiques. Une recherche sans résultat établit uniquement `not_found_in_scope` pour sa requête, ses filtres et sa date. Si l'outil manque aussi, garder sa trace d'indisponibilité et le contrôle restant ; résultat `unknown`. Aucun accès prospect, contact, paiement ou formulaire envoyé pour ce parcours URL seule.

## Journal et enregistrement

Conserver le journal `version: 1` des tentatives externes. Les destinations liées ordinaires gardent leur format existant. Pour la recherche, ajouter :

```json
{
  "version": 1,
  "attempts": [{
    "id": "search-01", "topic": "google_search",
    "url": "https://search.example/results", "status": "retrieved",
    "observed_at": "2026-10-29T12:00:00+00:00", "source_id": "search-copy",
    "operation": "search_then_read", "query": "Nom vérifié offre",
    "provider": "fournisseur réellement utilisé", "geography": "France",
    "window": "instantané du 29 octobre 2026"
  }],
  "public_research": {
    "version": 1,
    "entity": {"name": "Nom vérifié", "source_ids": ["official-page"], "match_reason": "Identifiants publics concordants"},
    "topics": [{"topic": "google_search", "attempt_ids": ["search-01"], "conclusion": "observed", "limits": "Portée exacte"}]
  }
}
```

Cet extrait montre une entrée ; le journal de recherche complet contient les quatre topics séparés, chacun avec tentative et limite. `conclusion` vaut `observed`, `not_found_in_scope` ou `unknown`. Chaque tentative porte ID unique, requête, opération, fournisseur réel, pays/périmètre et période. Enregistrer les copies publiques de résultats/pages utiles avec leur localisateur exact avant `discovery reconcile RUN_DIR --report JOURNAL`. Si l'URL du résultat diffère de la page lue, garder les deux preuves séparées.

Pour `unavailable`, garder `reason`, `trace_source_id` vers la preuve locale d'échec ou de capacité indisponible, et `fallback: {"attempt_id": "autre-tentative"}` du même topic, ou `fallback: {"reason": "limitation réelle empêchant aussi ce repli"}`. Une indisponibilité seule autorise uniquement `unknown`. Association à l'entité et traces rejoignent `discovery-channels`. Une modification invalide ses consommateurs. Les nouveaux runs portent ce contrat dès l'initialisation ; les anciens reçus ne sont pas requalifiés après coup.

`discovery channels RUN_DIR` vérifie liens, issues et empreintes. Officialité, lecture effective, indépendance des avis et conclusions restent à examiner par le rôle et la revue. Le contrôle ne fabrique aucune donnée de marché. L'analyse sépare fait nouveau, corroboration, reformulation, hypothèse et inconnu, puis réconcilie dans le modèle et le brief. Les mêmes bruts d'instrumentation ne deviennent pas deux preuves indépendantes en passant par deux skills.

## Reprises et remplacement des preuves périmées

Réconcilier le même fichier, au même chemin, avec les mêmes dépendances conserve son enregistrement, sa date et son approbation. Cela ne réactive pas un enregistrement périmé : fournir une nouvelle observation et ses preuves actuelles pour remplacer un journal devenu invalide. Une vraie modification du fichier ou de ses dépendances continue d'invalider les résultats qui en dépendent.

Le registre conserve les identifiants des journaux antérieurs. Les dépendances du bundle courant `discovery-channels` désignent les journaux utilisés pour les contrôles actuels. Un ancien journal remplacé et ses sources publiques inutilisées ailleurs restent historiques ; une source encore requise par un fait, une analyse ou un autre résultat continue de bloquer si elle est périmée. Le remplacement doit toujours couvrir les destinations et les quatre topics exigés. Il ne réutilise pas une recherche périmée pour combler un manque.

Un journal ordinaire sans clé `public_research` n'efface pas une recherche actuelle déjà réconciliée. En revanche, une clé présente avec `null`, une liste ou un autre type invalide est refusée. Les contrats présents acceptent uniquement l'entier `1` ; un booléen ou une version inconnue ne désactive pas le contrôle. Seule l'absence de la clé de contrat dans les métadonnées désigne un ancien run sans cette obligation.
