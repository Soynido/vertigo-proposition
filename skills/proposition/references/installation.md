# Installer le kit dans son propre espace

Le dépôt public fournit des skills et un runtime. Son utilisateur n'a besoin d'aucun droit d'écriture, d'aucune invitation de collaborateur, d'aucun fork et d'aucune clé GitHub pour le télécharger. Les comptes et permissions nécessaires à la création d'un environnement Codex Cloud sont une configuration de l'hôte. Aucun modèle ou effort particulier n'est imposé par ce kit.

## Codex Cloud : configuration initiale

1. Sur son propre compte GitHub, créer un dépôt **privé**, par exemple `vertigo-presentations`, avec un README. Ce dépôt est l'espace de travail du collaborateur. Ne pas coller l'URL du kit dans le champ « Repository name ».
2. Dans Codex Cloud, créer un environnement et connecter GitHub si nécessaire. Autoriser l'application utilisée par Codex sur ce seul dépôt privé, le sélectionner, puis commencer la préparation. Si la liste est vide, vérifier cette autorisation et actualiser. Aucun accès en écriture à `Soynido/vertigo-proposition` n'est nécessaire.
3. Activer l'accès Internet de l'environnement. Le parcours collecte des domaines prospect, médias et sources externes : le preset limité aux gestionnaires de paquets ne suffit pas. Pour ce premier essai, choisir **All (unrestricted)** si la politique du workspace l'autorise ; sinon autoriser les destinations requises et déclarer les manques. Aucun secret fournisseur n'est nécessaire au parcours natif.
4. Dans le terminal de préparation, depuis la racine du dépôt privé, télécharger le kit dans un checkout séparé des skills et des livrables :

```bash
WORKSPACE="$PWD"
KIT="$WORKSPACE/.vertigo/kit"
mkdir -p "$WORKSPACE/.vertigo"
git clone --depth 1 https://github.com/Soynido/vertigo-proposition.git "$KIT"
git -C "$KIT" remote set-url --push origin DISABLED
git -C "$KIT" rev-parse HEAD
```

Ce téléchargement ne pousse rien sur GitHub. La désactivation du push est une garde locale supplémentaire ; elle ne constitue pas un contrôle d'accès. Les droits du compte restent ceux de GitHub. Si `KIT` existe déjà, l'inspecter avant une mise à jour ; ne pas écraser un dossier ni supprimer un environnement utilisateur. Lire le README, `AGENTS.md`, `scripts/setup.py` et `scripts/install.py` du checkout avant exécution.

5. Installer le kit avec l'interpréteur **Python 3.11+** disponible :

```bash
python3 "$KIT/scripts/setup.py" --workspace "$WORKSPACE" --browser --with-upstream --with-presentations
```

Cette commande crée le venv du checkout, installe les paquets et hashes du profil présentations, installe Chromium, copie les **neuf skills et toutes leurs ressources** dans `$WORKSPACE/.agents/skills`, récupère les cinq distributions verrouillées et lance les contrôles. Marketingskills est une sélection explicite des deux méthodes de recherche, avec leurs références et licence ; les quatre autres familles restent complètes. Elle ne change pas les skills globaux ni la configuration MCP. Le reçu privé est `$WORKSPACE/.vertigo/setup.json`.

Sur **Linux avec autorisation explicite d'installation système et processus root**, ajouter `--with-system-deps` à cette même commande. Ce choix installe les bibliothèques système de Chromium ainsi que `libreoffice-impress` et `fonts-dejavu-core` via apt. L'installateur ne lance jamais `sudo`, ne crée pas de compte et n'élève pas ses droits. Sans cette capacité, faire préparer les dépendances par l'administrateur de l'environnement ou garder le blocage explicite. Sous macOS/Windows, fournir un renderer LibreOffice/soffice disponible et exécutable ou qualifier une capacité de présentation de l'hôte ; aucun gestionnaire système n'est lancé automatiquement.

6. Vérifier le reçu et compléter les capacités de l'hôte ci-dessous, puis publier l'environnement. Conserver le checkout : les skills installés référencent son Python. Dans une **nouvelle tâche** issue de cet environnement, relire le reçu et exécuter le diagnostic installé avant le travail client :

```bash
python3 "$WORKSPACE/.agents/skills/proposition/scripts/proposition.py" doctor --presentations
```

Les variables shell d'une phase de préparation ne sont pas un contrat de persistance. Dans une nouvelle tâche, résoudre `WORKSPACE` depuis le projet courant et le chemin du skill réellement installé. Ne pas supposer qu'un outil personnel du poste local est présent dans Cloud. L'état effectivement retrouvé et le doctor tranchent ; la préparation locale et la CI ne prouvent pas la persistance dans le compte du collaborateur.

Les configurations et livrables restent dans cet espace privé. Le cache des distributions publiques utilise `PROPOSITION_UPSTREAM_CACHE`, sinon `XDG_CACHE_HOME/vertigo-proposition/upstreams`, sinon `~/.cache/vertigo-proposition/upstreams` ; il ne contient pas les données prospect. Les sources vérifiées sont réutilisées entre propositions sans téléchargement supplémentaire lorsque leurs empreintes restent valides. Exclure `.vertigo/`, `.agents/skills/` et les sorties générées des commits automatiques de son dépôt de travail ; aucun commit ni push n'est nécessaire pour installer ou publier l'environnement Cloud. Les runs sont créés **hors du checkout du kit**, par exemple dans `$WORKSPACE/outputs` avec `init --runs-root`. Ne pas écrire de présentation ou de preuve prospect dans le dépôt public.

7. Dans la nouvelle tâche, le message utilisateur est seulement :

```text
https://github.com/Soynido/vertigo-proposition
<URL réelle du prospect>
```

L'agent lit le README de cette révision et le `proposition/SKILL.md` effectivement installé. Si plusieurs versions ou anciens plugins exposent le même nom, résoudre et consigner les fichiers de cette installation ; ne pas substituer leurs règles. Aucun brief, ancien contexte client ou rappel créatif n'est ajouté. La configuration technique initiale ne certifie pas le résultat du test autonome.

Sources officielles de la procédure Cloud : [environnements](https://learn.chatgpt.com/docs/environments/cloud-environments), [démarrage](https://learn.chatgpt.com/docs/cloud). Leurs interfaces et capacités peuvent évoluer ; relever la surface réellement utilisée.

## Paquets, outils et limites

| Besoin | Ce que fournit le kit | Vérification restante |
|---|---|---|
| Runtime | Python 3.11+, Git ; paquets Python et dépendances transitives verrouillés | Python et Git doivent être disponibles dans l'environnement |
| Navigation et PDF | Playwright, Chromium, extraction PDF, rendu PDFium et Pillow | Le doctor lance le navigateur ; les parcours réels, modales et scroll restent vérifiés sur le prospect |
| PPTX local | Profil optionnel `--with-presentations` : python-pptx 1.0.2 et dépendances verrouillées | Le profil nécessite LibreOffice/soffice pour son test de rendu local |
| Édition/rendu PPTX | `doctor --presentations` crée, rouvre, modifie, rend et rasterise une diapositive fictive avec texte et image séparés | Ce test mécanique ne prouve pas la fidélité du deck client, sa lisibilité ou sa qualité |
| Méthodes | Quatre sources à commits verrouillés : SEO/GEO, Impeccable, Apple Design et Scroll Craft | Chargées et appliquées avec reçus `native`, `adapted` ou `unavailable` ; un téléchargement n'est pas une exécution |
| Recherche et inspection visuelle | Capacités de l'agent hôte à inventorier | Accès aux sources et lecture des pixels réellement exposés ; jamais un PASS déduit du pip install |
| Création/revues indépendantes | Contrat public et paquets minimaux | Nouveaux contextes sans historique privé réellement disponibles ; sinon gate indépendant `BLOCKED` |
| Génération d'image et Sites | Facultatifs, s'ils sont autorisés et disponibles | Sans génération, utiliser les médias authentiques ; l'absence de Sites ne remplace pas la source HTML/CSS |
| Cloudflare et fournisseurs SEO | Facultatifs, uniquement si déjà autorisés et configurés | Aucun compte, crédit ou accès prospect exigé pour installer le parcours natif ; aucune activation automatique |
| MCP | **Aucun serveur MCP obligatoire pour le runtime local** | Un outil MCP utile doit être exposé, autorisé et essayé ; installer une dépendance Python n'installe pas un MCP |
| Connecteurs privés / publication | Hors du starter public | Autorisation et configuration distinctes ; aucune publication, aucun email ou déploiement implicites |

Le profil local PPTX fournit une bibliothèque et un contrôle d'outils. Il n'ajoute aucun exporteur de proposition, gabarit universel ou nouvelle procédure créative au moteur. Les sources HTML/CSS, la structure modifiable et les contrôles de fidélité restent ceux du contrat de livraison.

Le Cloud peut ne pas exposer les outils natifs de navigation/ordinateur du desktop. Le navigateur **piloté par code** doit réellement fonctionner dans cet environnement ; la présence d'un package ne suffit pas. Les capacités d'isolation et d'inspection visuelle doivent être vérifiées indépendamment. Garder chaque blocage localisé, sans déclarer le workflow complet prêt à partir du seul statut de l'installation.

## Local, mise à jour et contrôle

Le même `--workspace` fonctionne dans un dossier local existant distinct du kit. Un consommateur prépare ce dossier et utilise les mêmes commandes, sans configurer Codex Cloud. Le mode historique `--dest` reste disponible ; sans `--workspace` ni `--dest`, la destination historique est `~/.codex/skills`.

Une mise à jour gérée utilise `--update`, après vérification de la nouvelle révision et des scripts. Elle refuse d'écraser des skills modifiés ou non gérés. Les caches de méthodes verrouillées peuvent être réutilisés ; aucune donnée client n'est préchargée. Ne pas changer une installation en cours de qualification pour sauver un test.

`PASS` dans le reçu couvre **l'installation et les outils locaux essayés**. Les capacités d'hôte restent `NOT_VERIFIED_BY_INSTALLER`, et l'E2E prospect `NOT_RUN`, jusqu'à leurs preuves réelles. La qualification finale demeure un test neuf aux deux URL seules avec examen des PDF/PPTX exacts.
