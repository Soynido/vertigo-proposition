# Prétraitement public optionnel

Au passage collecte → modèle entreprise, exécuter `preprocess RUN_DIR` via la CLI installée. Le profil choisit `parameters.preprocess_mode=auto|codex|cloudflare` ; défaut `auto`. Le drapeau `--mode` sert à qualifier une route. Aucun nouveau fournisseur n'est requis pour le mode Codex.

## Paquet et consommation

Le moteur prend seulement les sources `COLLECTED`, `kind=public`, `audience=public`, fichier texte `.txt`/`.md` régulier et empreinte actuelle. Vérifier la provenance avant cet enregistrement ; un dossier CRM n'est pas une copie publique. Les sources privées, autres formats, textes suspects de secrets et plafonds dépassés sont exclus du paquet distant avec motif. Ils restent à traiter localement, jamais considérés absents ou analysés.

`packet.json` conserve identifiants, URL sans paramètres, dates, empreintes et offsets ; les textes sont découpés sans suppression de portion. Les extraits identiques après normalisation sont dédupliqués, tous leurs localisateurs restent présents. Le modèle reçoit seulement les identifiants de contenu et les textes nettoyés, une question de sujet par extrait. Aucun profil, cookie, header, clé, instruction interne ou registre de notes n'est transmis.

**Sortie à consommer dans les deux modes :** lire `native_task_path`, `packet_path`, puis `suggestions_path` si disponible ; revenir aux fichiers primaires utiles. Réconcilier offre, publics, voix, parcours, acquisition et instrumentation dans le modèle entreprise existant. Conserver les contradictions et inconnus. `SUGGESTIONS_READY` signifie classement disponible, jamais faits vérifiés ni PASS ; `CODEX_REQUIRED` demande le même travail local. Aucune sortie « other » ou de faible confiance ne retire une preuve, notamment cookies/tracking. Les contrôles Discovery, le brief et l'exploration créative restent exigés.

## Configuration privée de l'option

Sans fichier local : zéro requête Cloudflare, zéro installation Wrangler/SDK, zéro attente de login. `codex` interdit les appels distants. Pour un poste déjà autorisé, fichier `~/.config/vertigo-proposition/cloudflare.json` ou chemin donné par `VERTIGO_CLOUDFLARE_CONFIG` :

```json
{
  "account_id": "IDENTIFIANT_LOCAL_32_HEXADECIMAUX",
  "free_plan_confirmed": true,
  "confirmed_at": "DATE_ISO_CONFIRMATION_WORKERS_FREE",
  "allow_paid": false,
  "auth_file": "CHEMIN_LOCAL_WRANGLER_CONFIG_DEFAULT_TOML"
}
```

Les valeurs restent hors repo et export. Le token vient de `CLOUDFLARE_AUTH_TOKEN`/`CLOUDFLARE_API_TOKEN` ou du fichier OAuth explicitement référencé, non expiré. Le runtime n'effectue aucun login/rafraîchissement ni activation de facturation. La confirmation du forfait Free doit dater de moins de 24 h ; c'est une attestation locale, pas une lecture de facturation. Compte Paid, forfait inconnu, attestation périmée, authentification absente/refusée ou quota atteint : voie Codex. Un login seul ne confirme pas le modèle ni la gratuité. Ne pas passer `free_plan_confirmed=true` sur un compte payant pour forcer l'appel.

Modèle candidat unique : `@cf/cloudflare/clef`. Une tentative par lot, quatre appels simultanés maximum, timeout réseau 20 s et échéance de phase 60 s. Aucun retry automatique, aucun second modèle ni nouveau crawl. La réponse doit contenir exactement les identifiants et probabilités attendus. Une erreur conserve paquet, résultats valides et travail local.

## Volume, cache et reçus

Cache local de décisions publiques sous `XDG_CACHE_HOME/vertigo-proposition/preprocess` (défaut `~/.cache`). La clé lie textes, découpage, modèle et questions/version ; les identifiants de sources propres au run restent dans le paquet local. Un lot identique peut donc être réutilisé dans un autre run sans renvoyer ses textes. Les échecs tentés sont eux aussi conservés : la reprise ne les relance pas silencieusement. Ne supprimer un reçu d'échec pour réessayer qu'après diagnostic d'un changement effectif, en enregistrant cette intervention.

Le cache partagé est plafonné à 64 MiB ; seules ses propres entrées anciennes sont évincées. Le reçu du run conserve les tentatives, même après éviction, pour éviter de répéter un appel raté. La lecture d'une copie locale est bornée à cinq secondes par le lecteur existant de `prepare-inputs`, sans réexploration iCloud. Au-delà du budget de préparation, les sources restantes demeurent un travail local explicite. Référencer les médias canoniques plutôt que les copier pour ce traitement textuel.

Le reçu du run donne requêtes, cache, extraits uniques versus localisateurs, volume et tokens d'entrée déclarés par le fournisseur, durée, résultats validés et motifs de repli. Les sorties détaillées restent sur disque ; la CLI retourne un résumé. Les tokens Codex et le coût par client restent inconnus s'ils ne sont pas exposés. Un classement rapide ne mesure pas la durée totale de collecte, analyse ou création.

La modification d'une source produit un autre paquet ; les décisions anciennes ne deviennent pas des faits sur la source actuelle. Le modèle public n'expose pas de hash de poids immuable : conserver date/version du contrat et cette limite de provenance. Un cache ne garantit pas une nouvelle inférence identique. La qualification du composant et l'E2E autonome du kit distribué restent distincts.

Références : [Clef](https://developers.cloudflare.com/workers-ai/models/clef/), [allocation Free et facturation](https://developers.cloudflare.com/workers-ai/platform/pricing/).
