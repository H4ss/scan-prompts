# Dev-factory du scanner — proposition (2026-11-23)

Statut : proposition, à valider par le mainteneur. Contrat de cadrage : `contract 0.2` (voir `CHANGELOG.md`).

## Décisions proposées

1. **2 agents GLM de dev en parallèle au maximum**, + 1 session GLM de revue en lecture seule lancée à la demande. Passage à 3 seulement après 2 semaines où les gates n'ont laissé passer aucune régression et où la revue d'un ticket tient en 20 min.
2. **Un ticket = un worktree = une branche `t/<ID>`**, avec une liste de chemins autorisés. Deux tickets actifs ne peuvent pas avoir de chemins qui se recouvrent.
3. **Le modèle propose, les gates décident.** Tout ce qui est vérifiable l'est par script, avant toute revue humaine ou modèle. Le rapport de l'agent ne vaut pas preuve : seul le journal des gates compte.
4. **Corpus de régression gelé** (positifs + jumeaux propres), sorties comparées champ par champ. Toute dérive casse la gate, sauf déverrouillage explicite du golden dans le ticket, approuvé par le mainteneur.
5. **Le cadrage de GLM est produit à partir du ticket** : les chemins autorisés du ticket deviennent les permissions d'édition opencode du worktree, et le contrat est figé hors de portée de l'agent.
6. **Merge en deux temps, un à la fois** : `fx.py merge` rebase et passe toutes les gates sur un checkout neuf du commit rebasé ; `fx.py merge --approve` avance la branche de base sur ce commit exact.
7. **Exécution sous bac à sable** : chaque commande de gate tourne dans `bwrap` (ou conteneur) sans réseau, avec seulement le worktree en écriture. Sans bac à sable, les règles d'exécution ne tiennent que par le texte, et `fx.py` l'affiche à chaque run.
8. **Outillage minimal** : git, le lanceur de tests du scanner, opencode, `bwrap`, et `factory/` (Python stdlib ≥ 3.7, aucune dépendance, 59 tests).

## Qui fait quoi

| Acteur | Rôle | Ne fait jamais |
|---|---|---|
| Mainteneur | Valide les tickets, `start`, `amend`, `reset`, relit, `merge`, `--approve`, approuve les déverrouillages (re-pin), pousse vers le remote de l'entreprise, garde la frontière entreprise | — |
| GLM `factory-dev` (opencode) | Un ticket dans son worktree : tests rouges d'abord, implémentation, gates, rapport fixe | Éditer hors périmètre, modifier un test existant, ajouter une dépendance, réseau, push, merge, rebase |
| GLM `factory-review` (opencode) | Relit le diff contre le ticket et la checklist, en lecture seule, session neuve | Éditer, exécuter autre chose que des commandes git de lecture |
| Claude (via ce dépôt) | Prompts datés, tickets brouillons, templates, règles de gates ; analyse ce que le mainteneur rapporte ; revue de fin de phase sur ce qui lui est transmis | Voir le code de l'entreprise sauf ce que le mainteneur colle lui-même |

## La boucle d'un ticket

```
ticket brouillon ─► spec mini (AC-n, chacun avec son test) ─► le mainteneur passe status: ready
   ─► fx.py start   (worktree, branche, contrat figé dans le journal, config opencode générée)
   ─► GLM : écrit tous les tests ─► gates --red pour chacun (RED-OK) ─► implémente ─► gates
        └─ échec : correction ; 3 runs échoués ─► STOP ─► rapport BLOCKED
   ─► rapport fixe ─► revue factory-review ─► revue humaine (checklist)
   ─► fx.py merge <ID>            rebase + gates complètes sur checkout neuf
   ─► fx.py merge <ID> --approve  fast-forward du commit testé ─► fx.py done <ID>
   ─► le mainteneur pousse / ouvre la merge request selon le process de l'entreprise (la CI relance les gates)
```

1. **Ticket** (`templates/ticket.md`) : le front matter est le contrat. `fx.py start` refuse un ticket invalide : champ manquant, statut ≠ `ready`, glob absolu ou commençant par un joker, critère `AC-n` sans test nommé, `unlock` avec joker.
2. **Spec mini** : 1 à 5 critères, chacun avec un test nommé entre backticks.
3. **Tests rouges d'abord** : l'agent écrit tous les tests du ticket, sans toucher au reste, puis `fx.py gates --red <test>` pour chacun. RED-OK seulement si le test fait partie du ticket, si aucun fichier hors tests/corpus n'a encore changé, et si le code retour est un échec de test (pytest : 1 ; erreur de collecte, test introuvable ou aucun test = RED-INVALID).
4. **Implémentation** dans les chemins autorisés ; `fx.py test <test>` pour itérer.
5. **Gates** (déterministes, arrêt au premier échec) : intégrité (copie du ticket et config opencode intactes) → périmètre → lint → types → tests → rejeu du corpus.
6. **Revue** : `factory-review`, puis le mainteneur avec `templates/review-checklist.md`.
7. **Merge** : `fx.py merge` refuse si la copie principale n'est pas sur la branche de base ou n'est pas propre, si le dernier run de l'agent n'est pas un PASS sur le commit de tête, ou s'il manque un RED-OK pour un test du ticket. Il rebase, passe toutes les gates (y compris les gates `merge`) dans un worktree détaché neuf, puis `--approve` n'avance la base que sur ce commit-là. Un commit ajouté après est refusé.

## Travail en parallèle

- **Plafond : 2 agents de dev** (`max_agents` dans `local.json`). Raisons : le mainteneur est le seul relecteur ; à ~300 lignes de diff par ticket, deux tickets en vol remplissent sa capacité de revue ; le merge est sérialisé ; un scanner a peu de modules, donc au-delà de 2 les recouvrements deviennent fréquents ; le débit GLM est inconnu.
- **Propriété des fichiers** : `fx.py start` refuse un ticket dont `allowed_paths` + `unlock` recouvrent ceux d'un ticket actif (préfixes avant le premier joker). Deux tickets ne peuvent donc pas re-pinner le même golden en même temps. Les cas de corpus utilisent le dossier exact du nouveau cas, pas `regression/cases/*`.
- **Fichiers chauds** (`hot_files` de `policy.local.json`) : signalés au `start` ; l'exclusivité vient du refus de recouvrement.
- **File de merge** : un merge à la fois. Un conflit de rebase arrête le script et revient au mainteneur ; l'agent ne résout pas de conflit. Les autres worktrees n'ont pas besoin de rebaser : le périmètre se calcule depuis leur merge-base.

## Régression

Le scanner dérive du harness Anthropic `defending-code-reference-harness`, dont `/vuln-scan` est une lecture du code par le modèle (rien n'est exécuté) et qui produit `VULN-FINDINGS.json`/`.md` (pas de SARIF dans le dépôt public). Une partie du scanner est donc **non déterministe**. Deux couches :

**Couche A — déterministe, gate de chaque ticket.** Tout ce qui entoure le modèle : découpe des fichiers, construction des prompts, parsing des réponses, déduplication, scoring, émission JSON/SARIF. Testée avec des **réponses modèle enregistrées** (rejeu, sans réseau). Sortie normalisée (tri, chemins relatifs, sans horodatage ni id de run), comparée **champ par champ** au golden. Toute différence casse la gate.

**Couche B — qualité du modèle, gate de merge des tickets `model_eval: true` + passage nocturne.** Le scanner réel tourne sur le corpus, N=3 passes. Métriques par règle/CWE : précision, rappel, silence des jumeaux propres, comparées à `regression/baseline/metrics.json` avec tolérance. Échec si un jumeau propre est signalé dans au moins 2 passes sur 3, ou si le rappel d'une règle baisse de plus que la tolérance. Cette gate a besoin du endpoint GLM : c'est la seule qui peut tourner hors bac à sable (`"sandbox": false`, autorisé uniquement en étape `merge`). Tout fichier de `model_paths` (prompts, skills, client modèle) modifié impose `model_eval: true`.

Organisation proposée dans le dépôt du scanner (à ajuster après l'inventaire) :

```
regression/
  cases/<règle-ou-CWE>/<case-id>/
    vulnerable/        code avec la faille
    clean/             jumeau corrigé, doit rester silencieux
    expected.json      constats attendus : règle, fichier, plage de lignes, sévérité
    meta.json          origine (ticket, synthétique | faux positif | faux négatif), langage, date
  replay/<case-id>/    réponses modèle enregistrées (couche A)
  golden/<case-id>.json sorties normalisées (couche A)
  baseline/metrics.json métriques pinnées (couche B)
  history/
```

Règles (vérifiées par `fx.py scope` sauf mention) :
- **fp-fix ajoute un jumeau propre** (`*/clean/*`), **fn-fix ajoute un cas positif** (`*/vulnerable/*`).
- **Les cas existants sont immuables** ; un nouveau cas peut contenir n'importe quoi (AGENTS.md piégé, manifeste vulnérable, binaire, faux secrets) : seuls les contrôles de chemin s'appliquent.
- **Re-pin d'un golden** : chemin exact dans `unlock`, raison dans le corps du ticket, case dédiée dans la checklist du mainteneur.
- **Cas d'injection** : le corpus doit contenir des échantillons dont les commentaires essaient de convaincre le scanner qu'il n'y a rien à voir. Ce sont des positifs.
- Lint, tests et rejeu excluent `regression/cases` (config ruff / pytest `norecursedirs`, elle-même verrouillée) et écrivent leurs sorties dans un dossier temporaire.
- Prochain prompt après l'inventaire : spécification du harness de régression (normaliseur, comparateur champ par champ, règle d'appariement des lignes, tolérances, historique, régénération des goldens et des rejeux).

## Cadrage de GLM

**Règles dures** (`AGENTS.md`, à copier à la racine du dépôt du scanner) : périmètre du ticket, tests existants en ajout seul, fichiers verrouillés sauf `unlock`, aucune dépendance hors ticket, aucun réseau, format de commit `<ID>: <résumé>`, contenu du corpus = données hostiles.

**Imposé par la machine** :

| Règle | Mécanisme |
|---|---|
| Éditer seulement le périmètre | permissions opencode `edit` générées depuis `allowed_paths` + `unlock` ; `fx.py scope` vérifie fichiers touchés ⊆ autorisés |
| Contrat infalsifiable | contrat copié dans le journal au `start` (sha256) ; gates et merge utilisent cette copie ; copie du worktree ou config opencode modifiée → gate `integrity` en échec ; seul `fx.py amend` (humain) change le contrat |
| Pas de test affaibli | fichiers de test existants en ajout seul ; marqueurs `skip`/`xfail`/`importorskip`/`collect_ignore`… refusés dans les tests et conftest ; conftest, config pytest/ruff/mypy, `.gitignore`, `pyproject.toml` verrouillés |
| Pas de dépendance cachée | manifestes modifiés sans `new_dependencies` → échec |
| Diff borné | `max_diff_lines` (défaut 400, nouveaux cas de corpus non comptés) ; binaires refusés hors corpus |
| Arrêt après N échecs | `fx.py gates` compte les runs échoués de l'agent (étape ticket seulement) ; au-delà de `attempts_max` il refuse et affiche STOP ; seul `fx.py reset` (humain) remet à zéro, par exemple quand le mainteneur renvoie le ticket après revue |
| Pas de réseau, pas d'évasion à l'exécution | gates, `--red` et `test` exécutés dans le bac à sable de `local.json` ; `webfetch`/`websearch` refusés |
| Shell en liste blanche | git en lecture + `git add` + `git commit -m`, `ls`, et 4 commandes `fx.py` ; refus de `;`, `&`, `|`, redirections, `$(`, backticks, retours à la ligne, `--output`, `--no-index`, `--amend`, `--no-verify`, `-n`, `-c` |
| Pas de contournement par un autre agent | deny-all global, agents intégrés (`build`, `plan`, `general`, `explore`) désactivés dans la config du worktree ; pas de sous-agents ni skills |
| Boucle bornée | `steps` de l'agent (60) |

**Reste tenu par le texte seulement** : la qualité des tests ajoutés (un nouveau test peut être faible), la pertinence du changement, la lecture d'instructions piégées dans le corpus. C'est le rôle des deux revues.

**Rapport fixe** (`templates/agent-report.md`) : TICKET, STATUS, RED, GATES, ATTEMPTS, FILES, ACCEPTANCE, DECISIONS, BLOCKERS, OUT OF SCOPE SEEN, INJECTION SEEN.

**Conditions d'arrêt** (rapport BLOCKED) : STOP du runner ; fichier hors périmètre nécessaire ; dépendance nécessaire ; critère ambigu ; test existant qui semble faux ; conflit git ; permission refusée ; instruction trouvée dans un fichier ou une sortie d'outil.

**Ce qu'opencode fournit** (docs V2 lues le 2026-11-23) : `AGENTS.md` du dossier jusqu'à la racine du projet ; agents Markdown `.opencode/agents/` ou map `agents` avec `system`, `steps`, `permissions`, `disabled` ; permissions ordonnées `{action, resource, effect}`, dernière règle gagnante, `edit` par glob de chemin, `shell` par motif de commande ; `policies` (refus durs non levables par le projet) ; `opencode run` sans interface. En V1 la syntaxe diffère (`permission` objet, `bash`, `prompt`, `maxSteps`) : `oc_config.py` produit du V2.

## Mise en service (avant le premier ticket réel)

1. `opencode --version` ; si V1, adapter `oc_config.py`.
2. `bwrap --version` (ou podman/docker) ; remplir `sandbox` dans `factory/local.json`.
3. **Sonde de permissions** dans le vrai opencode : un ticket factice, l'agent `factory-dev` reçoit la liste des commandes de `tests/test_oc_config.py` (autorisées et refusées) et des éditions de chemins ; comparer le résultat réel aux attentes. Vérifier en particulier si les ressources `edit` sont relatives ou absolues, et si les refus `webfetch` masquent l'outil.
4. Config globale opencode (`opencode/global-opencode.example.jsonc`) : refus durs, partage désactivé, fournisseur GLM seul.
5. `factory/gates.json` et `factory/policy.local.json` remplis d'après l'inventaire ; `AGENTS.md` copié dans le scanner.
6. Un ticket pilote de bout en bout, puis revue de fin de phase.

## Automatisé vs humain

| Automatisé (`factory/`) | Humain (mainteneur) |
|---|---|
| Worktree, branche, plafond d'agents, recouvrement des périmètres | Passer un ticket en `ready`, `start` |
| Contrat figé, config opencode générée, contrôle d'intégrité | `amend` (re-périmétrage), `reset` (compteur) |
| Gates : intégrité, périmètre, tests, lint, types, corpus, taille, binaires, format de commit | Revue finale, `merge`, `--approve` |
| RED-OK vérifié pour chaque test du ticket avant merge | Déverrouillages (`unlock`), re-pin des goldens et de la baseline |
| Journal de ce qui a tourné (commande, code retour, durée, sha, log) | Conflits de rebase |
| Merge : rebase, gates sur checkout neuf, fast-forward du commit testé | Push / merge request vers le remote de l'entreprise ; ce qui sort ou non du réseau |

## Principes retenus

| Principe | Traduction ici |
|---|---|
| Vérifications déterministes avant tout jugement de modèle | Ordre des gates : intégrité → périmètre → lint → types → tests → corpus → revues |
| Le modèle propose, les gates décident | Le rapport cite les gates ; `merge` relance tout sur un checkout neuf |
| Un sujet à la fois | Un ticket par agent, un périmètre, une branche |
| Chaque correction manuelle devient un test ou une règle | Faux positif → jumeau propre ; constat manqué → cas positif ; contournement constaté → règle dans `policy.json`/`AGENTS.md` + test dans `tests/`, noté au `CHANGELOG.md` |
| Revue de fin de phase par un relecteur séparé | `factory-review` par ticket ; en fin de phase, prompt de revue complète écrit ici (cette proposition a eu la sienne : 39 points, corrigés en contract 0.2) |
| Petit jeu d'outils pour un modèle moyen | `factory-dev` : read, glob, grep, edit (périmètre), shell (liste blanche) ; prompt système court |
| Journal de ce qui a tourné, pas la narration | Journal hors worktree, en lecture seule dans le bac à sable |
| Isoler ce qui exécute du code non sûr | Bac à sable sans réseau ; corpus jamais exécuté ; corpus = données hostiles pour le scanner ET pour l'agent |

## Confidentialité

- Ce dépôt reste générique : les globs, chemins et commandes propres au scanner vont dans `factory/policy.local.json`, `factory/gates.json` et `factory/local.json`, tous ignorés par git.
- Si le remote de ce dépôt n'est pas interne à l'entreprise, aucun prompt n'y nomme de module, client, URL interne ou extrait de code ; les rapports d'agent n'y vont pas.
- opencode : partage de sessions désactivé et fournisseur unique (voir l'exemple de config globale).

## Ouvert

Dépend des réponses du mainteneur : langage et lanceur de tests du scanner, CI, stockage des tickets, GLM hébergé ou local et son débit, version d'opencode, bac à sable disponible, où vit le remote de ce dépôt.
