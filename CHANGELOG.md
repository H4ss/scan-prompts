# Changelog

Contrat de cadrage (AGENTS.md, templates, policy.json, scripts factory). Une entrée par changement de règle, avec la raison.

## contract 0.2 — 2026-11-23

Suite à la revue de fin de phase (relecteur séparé, 39 points dont 10 bloquants, plusieurs reproduits).

- Contrat figé dans le journal au `start` (sha256) ; gates et merge l'utilisent ; gate `integrity` si la copie du worktree ou la config opencode change ; `fx.py amend` (humain) pour re-périmétrer. Raison : élargir `allowed_paths` dans la copie du worktree passait le merge.
- Commandes agent sans `--ticket/--repo/--base` (ticket déduit de la branche `t/<ID>`, base stockée au `start`) ; `allow_abbrev=False` ; reset du compteur déplacé vers `fx.py reset` (humain). Raison : `--hu`, `--base HEAD`, `--ticket` d'un autre id contournaient compteur et périmètre.
- Merge en deux temps : gates sur un worktree détaché neuf du commit rebasé, `--approve` avance la base sur ce commit exact ; refus si la copie principale n'est pas sur la base, si l'agent n'a pas de PASS sur la tête, s'il manque un RED-OK. Raisons : merge sur la mauvaise branche, commit tardif non testé, conftest caché par un `.gitignore`.
- Bac à sable configurable (`sandbox` dans `local.json`, `bwrap` proposé) pour gates, `--red` et `test` ; pytest brut retiré de la liste blanche ; `fx.py test <id>`.
- `--red` : test du ticket uniquement, code retour d'échec de test seulement (`fail_codes`, défaut `[1]`), refusé si du code hors tests a déjà changé.
- Tests existants en ajout seul ; marqueurs de contournement élargis ; fichiers de config de tests, `.gitignore`, `pyproject.toml`, goldens verrouillés sauf `unlock` (exact, remplace `repin_golden`).
- Liste de refus shell élargie (retour à la ligne, `&`, `$(`, backticks, `<`, `--output`, `--no-index`, `--amend`, `-n`, `-c`).
- Config opencode : deny-all global, agents intégrés désactivés, `external_directory` limité à `fx.py`.
- Nouveaux cas de corpus exemptés des contrôles protégé/manifeste/binaire ; binaires refusés hors corpus ; `fp-fix`/`fn-fix` doivent ajouter leur cas ; `model_paths` impose `model_eval`.
- Recouvrement des périmètres incluant `unlock` ; globs `allowed_paths` relatifs et ancrés ; critère sans test refusé.
- Parsing git en `-z` (chemins non ASCII), timeouts qui tuent le groupe de processus, Python ≥ 3.7, front matter avec BOM / `#` / zéros en tête.
- Confidentialité : `local.json`, `gates.json`, `policy.local.json` ignorés par git ; partage de session opencode désactivé dans l'exemple global.
- Lint des prompts : ids en double, prompts figés comparés à `HEAD`.
- Prompt `2026-11-23-02-project-inventory` remplace `-01` (branche par défaut, versions python3/opencode, configs agent existantes, bac à sable disponible, conftest ; la suite n'est plus lancée par l'agent).

## contract 0.1 — 2026-11-23

- Création : DEV-FACTORY.md (proposition), AGENTS.md (brouillon), templates ticket / rapport / checklist / prompt.
- factory/ : `fx.py` (start, list, scope, gates, gates --red, merge, done, opencode-config), journal hors worktree, plafond de 2 agents, refus des périmètres qui se recouvrent.
- opencode : agents `factory-dev` et `factory-review`, config par worktree générée depuis le ticket (syntaxe V2 documentée au 2026-11-23).
- Prompt `2026-11-23-01-project-inventory`.
