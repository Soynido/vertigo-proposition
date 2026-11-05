# Licences et provenance

Le code original et les méthodes originales de ce dépôt sont sous MIT. La marque et le logo Vertigo ne sont pas accordés par cette licence. Le paquet `skills/proposition/resources/web/agency` distribue les graphiques agence autorisés selon ses conditions séparées, sans licence de marque générale. Aucun dossier prospect, historique privé ou tarif d’entreprise n’est distribué.

Les distributions de skills tierces ne sont pas copiées dans ce dépôt. Le verrou dans `skills/proposition/scripts/proposition_runtime/data/upstream-lock.json` indique leurs révisions immuables, points d'entrée et licences. Le téléchargement conserve le dépôt complet ou la sélection explicite annoncée ci-dessous, sa licence et un inventaire avec empreintes. Leur code n'est pas exécuté pendant l'installation.

| Famille | Projet et licence annoncée |
|---|---|
| SEO/GEO | [claude-seo](https://github.com/AgriciDaniel/claude-seo), MIT ; vérifier les notices des références et outils additionnels avant réutilisation |
| Impeccable | [pbakaus/impeccable](https://github.com/pbakaus/impeccable), Apache-2.0 |
| Scroll Craft | [nateherkai/scroll-craft](https://github.com/nateherkai/scroll-craft), MIT |
| Apple Design | [emilkowalski/skills](https://github.com/emilkowalski/skills), MIT |
| Recherche marketing | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills/tree/e85f3cbc2e4a79bf33b2a12e9bdd9087d414735b), MIT, copyright Corey Haines ; sélection de `product-marketing` 2.2.0, `customer-research` 2.0.4, leurs dossiers de références complets et `LICENSE` |

La sélection Marketingskills est récupérée par blobs Git dont tailles et empreintes sont confrontées à l'arbre épinglé. Le reçu dit `source_scope=selected_paths`, conserve la liste exacte et n'annonce pas un dépôt complet. Le lien racine `CLAUDE.md` et les autres chemins hors sélection ne sont ni téléchargés ni suivis. Tout lien/submodule dans les sources requises reste refusé ; le mode dépôt complet conserve son refus général. Les références d'entretiens/enquêtes restent disponibles comme sources de méthode, sans autoriser leur exécution, contact, accès privé ou dépense dans le parcours public à URL seule.

Les références éditoriales sont citées aux endroits où elles servent ; une citation ne rend pas leur contenu redistribuable. Les méthodes ici sont rédigées pour ce projet. Aucun skill PDF/PPTX propriétaire d'un autre éditeur n'est embarqué.

Les dépendances Python sont verrouillées et installées depuis leurs distributions, qui conservent leurs notices : jsonschema (MIT), Playwright (Apache-2.0), pypdf (BSD-3-Clause), Pillow (licence HPND et composants tiers), pypdfium2 (Apache-2.0/BSD-3-Clause et PDFium avec notices propres), ainsi que leurs dépendances transitives. Chromium possède ses propres notices. Consulter les fichiers de licence des distributions installées pour les détails des composants.

Photographies, typographies, illustrations et données collectées gardent leurs droits. Une URL publique ou une bonne provenance ne constitue pas une autorisation de diffusion ou de retouche.


## Ressources web distribuées

- `resources/web/agency/MANIFEST.json` lie chaque ressource à sa provenance et à ses octets. Les graphiques VERTIGO et le poster studio gardent leurs droits selon `agency/LICENSE.txt` ; ils ne sont pas sous MIT. La transcription raster du logotype n’embarque aucune police propriétaire. Les sujets ou marques tiers d’un portfolio ne sont pas relicenciés.
- Les fichiers Poppins sont sous SIL Open Font License 1.1, copyright Indian Type Foundry ; la licence complète est `agency/OFL-Poppins.txt`. Les notices et noms réservés restent applicables aux variantes.
- Le code portable de mouvement est sous MIT avec provenance des adaptations et empreintes des références dans `resources/web/PROVENANCE.json`. Ces mécanismes ne distribuent ni projets client ni médias de ces projets.
- La CLI Vercel est installée séparément à la version exacte de `resources/toolchain/vercel/package-lock.json` ; ses distributions npm et dépendances conservent leurs licences/notices. L’installation n’exécute pas les scripts npm de ces paquets. Node/npm et les navigateurs Chromium/WebKit gardent leurs propres licences. Aucun token ou accès fournisseur n’est embarqué.
