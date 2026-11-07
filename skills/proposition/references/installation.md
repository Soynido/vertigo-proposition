# Installer le kit dans son propre espace

Le dépôt public est une distribution, pas le workspace prospect. Aucun droit d'écriture, invitation, fork ou clé GitHub n'est nécessaire pour le télécharger. Aucun modèle ou effort particulier n'est imposé. Le format standard installé est `web` ; le parcours `documents` reste disponible explicitement.

## Préparer une fois Codex ou Claude Code

Pour le suivi natif **Codex Desktop** dans la lane, ajouter explicitement à l'installation `--with-native-observer --native-model MODELE_CHOISI --native-effort EFFORT_CHOISI`. Ce réglage se fait une fois ; le futur prompt reste les deux URL. Il installe le transport Codex verrouillé dans un cache isolé et conserve l'abonnement connecté, sans remplacer le CLI global ni modifier son authentification. La lane doit disposer de `open_in_codex` pour son onglet ; cela n'en fait pas un MCP obligatoire pour le parcours Cloud ou Claude sans cet observateur. Un modèle indisponible bloque au lieu d'être remplacé. Lire [le démarrage natif](native-startup.md) pour la portée réelle de la trace et la distinction entre lanceur Desktop et arbre de production.

Créer ou sélectionner son propre workspace privé. Dans Codex Cloud, préparer un environnement personnel. Si l'interface demande un dépôt, sélectionner son propre dépôt privé (un README suffit), autoriser la connexion GitHub sur ce dépôt et actualiser la liste. Ne pas créer une copie sous le compte de Vertigo ni coller une URL dans « Repository name ». L'accès au kit public se fait par téléchargement, sans invitation de collaborateur.

Activer le réseau nécessaire aux sites prospect, médias/CDN, recherche publique, méthodes et à `api.vercel.com`/Vercel. Le preset de gestionnaires de paquets ne couvre pas toute la recherche. Dans l'interface Cloud actuelle, vérifier l'accès Internet public et les destinations autorisées, puis publier l'environnement. Une permission réseau ne fournit pas des identifiants.

Depuis la racine du workspace privé :

```bash
WORKSPACE="$PWD"
KIT="$WORKSPACE/.vertigo/kit"
mkdir -p "$WORKSPACE/.vertigo"
git clone --depth 1 https://github.com/Soynido/vertigo-proposition.git "$KIT"
git -C "$KIT" remote set-url --push origin DISABLED
git -C "$KIT" rev-parse HEAD
```

Si `KIT` existe, inspecter sa révision avant une mise à jour, sans écraser de fichiers. Lire son README, `AGENTS.md`, `scripts/setup.py` et `scripts/install.py` avant exécution. La garde locale de push n'est pas un contrôle de permissions GitHub. Aucun push n'est requis.

Préparer Python 3.11+, Git et Node/npm. Configurer une connexion Vercel personnelle autorisée à créer le support isolé : soit le login CLI local, soit une variable personnelle accessible à la tâche. Ne pas écrire un token dans une commande, un document ou le dépôt. Choisir son organisation une fois dans la CLI ou passer son identifiant par `--vercel-org` à l'installation.

```bash
python3 "$KIT/scripts/setup.py" --workspace "$WORKSPACE" --host codex \
  --browser --with-upstream --owner "NOM DU RESPONSABLE" --with-publication
```

Pour Claude Code dans son propre projet, remplacer seulement `--host codex` par `--host claude`. L'installateur crée le venv, installe les dépendances verrouillées, Chromium et WebKit, les neuf skills et leurs ressources, les méthodes épinglées et les instructions d'entrée propres à l'hôte. Codex reçoit `.agents/skills` et un bloc géré dans `AGENTS.md` ; Claude Code reçoit `.claude/skills` et `CLAUDE.md`. Le texte préexistant hors bloc est conservé. Les réglages privés sont dans `.vertigo/profile.json`, les reçus dans `.vertigo/setup.json` et `setup-HOST.json`. Conserver le kit : le lanceur installé référence son Python.

Sur Linux, `--with-system-deps` est une option explicite pour un processus root autorisé : elle installe les bibliothèques système des navigateurs. Aucun `sudo` ni élévation automatique. Pour le mode documentaire, ajouter `--delivery-format documents --with-presentations`, omettre `--with-publication` et fournir LibreOffice/soffice ; avec l'option système autorisée, le renderer est installé. Ce profil conserve python-pptx et ses contrôles d'édition/rendu. Il n'est pas nécessaire au web.

## Vercel : un lien normal, support géré une fois

Un lien Vercel appartient à un projet. L'option explicite `--with-publication` crée et vérifie automatiquement **un nouveau support isolé**, sans demander un projet au collaborateur et sans modifier un site existant. La CLI Vercel est verrouillée dans un cache séparé, sans remplacer une CLI globale. Comme Vercel réserve le premier déploiement d'un projet à sa production, l'installation publie uniquement une page technique fixe sans prospect. Ensuite chaque run utilise exclusivement une prévisualisation unique ; aucun domaine, alias ou déploiement de production client n'est changé.

La politique privée contient responsable, organisation, projet autorisé et référence d'accès ; aucun token en clair. Une installation interrompue conserve son reçu et réconcilie l'effet inconnu avant une nouvelle tentative. Ne pas créer un autre projet pour masquer un état incertain.

Pour une variable personnelle déjà configurée dans l'hôte, ajouter `--vercel-credential-ref env:VERTIGO_VERCEL_TOKEN` et l'organisation. Le kit garde seulement le nom de la variable. Dans l'interface Cloud actuelle, demander cette variable à l'environnement et la fournir depuis le coffre personnel comme **Environment variable**, car CLI et client HTTP doivent pouvoir la lire. Un simple `export` dans une préparation ne prouve pas sa présence dans une autre tâche. Dans les anciens environnements Cloud, les « secrets » réservés au setup sont retirés avant l'agent : ils ne suffisent pas pour cette référence runtime. Ne pas contourner cette limite en enregistrant un token dans les skills ou les sorties.

Sources officielles : [environnements Cloud actuels](https://learn.chatgpt.com/docs/environments/cloud-environments), [anciens environnements et portée des secrets](https://learn.chatgpt.com/docs/environments/cloud-environment). Relever l'interface réellement utilisée ; ces deux configurations ne sont pas interchangeables. Un test local ne prouve pas la persistance des accès dans le compte du collaborateur.

## Vérifier dans une nouvelle tâche

Résoudre le workspace et le lanceur depuis l'installation effectivement présente. Ne pas supposer que les variables du terminal de préparation ont persisté.

```bash
python3 "$WORKSPACE/.agents/skills/proposition/scripts/proposition.py" doctor --delivery-format web
```

Pour Claude, utiliser `.claude/skills` au lieu de `.agents/skills`. Vérifier que les neuf skills, méthodes, caches et ressources sont retrouvés et que les vrais navigateurs fonctionnent. L'hôte doit également exposer recherche, lecture des pixels et nouveaux contextes indépendants. Une installation de paquet n'atteste pas ces capacités. Après `init`, `web preflight RUN` relit les accès actuels et le projet autorisé **sans écriture fournisseur**, avant le travail prospect.

Les fichiers privés, `.vertigo/`, les skills installés et les livrables ne sont pas destinés aux commits de l'espace de travail. Les runs vivent hors du checkout du kit, par exemple dans `$WORKSPACE/outputs`. Les caches publics peuvent être réutilisés après vérification ; ils ne fournissent aucun résultat client.

Dans une nouvelle tâche du même environnement préparé, envoyer uniquement :

```text
https://github.com/Soynido/vertigo-proposition
<URL réelle du prospect>
```

L'agent retrouve l'entrée installée et initialise `web` explicitement. Aucun brief, rappel créatif ou ancien rendu à ajouter. Si une autre version du plugin existe, relever les fichiers réellement utilisés et suivre cette installation, sans mélanger les contrats.

## Portée des contrôles et mise à jour

Le doctor web teste Chromium/WebKit ; le doctor documentaire conserve le test PDF et, avec `--presentations`, la création/édition/rendu d'une fixture PPTX. Ni l'un ni l'autre ne juge le client, la créativité, la fidélité des livrables ou l'indépendance de l'hôte. Les quatre méthodes créatives et les deux méthodes marketing/recherche sont distribuées à leurs révisions verrouillées, avec références et licences. Réception, lecture, application adaptée et indisponibilité restent distinctes.

Aucun MCP, Cloudflare ou fournisseur IA payant supplémentaire n'est obligatoire. La génération d'image est facultative ; la matière authentique reste prioritaire. Sans une capacité essentielle, conserver un blocage précis au lieu d'inventer son usage. Aucun repli payant Anthropic.

Le mode historique `--dest` est conservé ; sans workspace/destination, il utilise `~/.codex/skills`. Une mise à jour explicite `--update` refuse d'écraser des skills ou un bloc géré modifiés. Ne pas changer une installation pendant un essai pour sauver son résultat.

`PASS` d'installation couvre les outils essayés, pas l'autonomie. La qualification exige les deux URL seules, les HTML/ressources/lien public exacts en web, ou les PDF/PPTX exacts en documents, avec qualité et durée évaluées séparément. La qualification Codex puis Claude Code et la répétabilité restent attachées aux cas réellement testés.
