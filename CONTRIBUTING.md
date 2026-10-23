# Contribuer

Installer Python 3.11+, puis les dépendances verrouillées. Exécuter `python scripts/test.py` dans l'environnement installé ; les tests navigateur nécessitent Chrome ou `python -m playwright install chromium`. Sur Linux : `PROPOSITION_BROWSER_CHANNEL=chromium`.

Pour une modification de comportement : reproduire le défaut par un test qui échoue, corriger, exécuter les tests concernés. À la promotion : une revue indépendante et la suite complète. Une preuve de qualité doit nommer les fichiers et leurs empreintes, pas seulement une branche ou un écran.

Pour une méthode : ajouter un cas concret dans `evals/cases/`, tester sans puis avec la guidance dans des contextes frais. Ne pas donner au testeur les critères attendus ou les verdicts antérieurs. Distinguer résultats observés, tests non exécutés et hypothèses. Lire `docs/maintaining-methods.md`.

Une nouvelle dépendance exige licence, révision immuable et utilité démontrée. Les notices, ressources référencées et limites d'exécution font partie du changement. Les données de test sont fictives ; aucun exemple de client réel ou règle interne d'entreprise ne doit être nécessaire au dépôt public.
