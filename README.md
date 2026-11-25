# scanner-prompts

Dépôt de pilotage de la dev-factory du scanner : prompts datés et versionnés pour GLM/opencode, templates, règles agent, scripts de gates. Aucun code du scanner ici.

- Design : [DEV-FACTORY.md](DEV-FACTORY.md)
- Règles agent (à copier dans le dépôt du scanner) : [AGENTS.md](AGENTS.md)
- Historique du contrat de cadrage : [CHANGELOG.md](CHANGELOG.md)

## Contenu

```
prompts/YYYY-MM-DD-NN-<slug>.md   prompts (en anglais pour GLM), un fichier par prompt
templates/                         ticket, rapport agent, checklist de revue, prompt
AGENTS.md                          règles dures pour les agents (brouillon à copier)
opencode/agents/                   prompts système factory-dev et factory-review
opencode/global-opencode.example.jsonc   refus durs, partage désactivé, fournisseur GLM
factory/                           fx.py et modules (Python stdlib >= 3.7)
  local.example.json               réglages machine -> local.json (ignoré par git)
  gates.example.json               commandes de gates -> gates.json (ignoré)
  policy.json                      règles génériques ; policy.local.json (ignoré) pour le spécifique
tests/                             tests des scripts factory
```

Tests : `python3 -m unittest discover -s tests`. Lint des prompts : `python3 factory/lint_prompts.py` (avant chaque commit).

## Cycle de vie d'un prompt

| status | sens | qui |
|---|---|---|
| `draft` | en cours d'écriture, modifiable, `version` +1 à chaque modification | Claude |
| `ready` | figé, peut être appliqué | Claude, après accord du mainteneur |
| `applied` | appliqué au travail | Mainteneur |
| `superseded` | remplacé par un prompt dont `supersedes` pointe ici | Claude |
| `withdrawn` | abandonné | Claude ou le mainteneur |

- Nom : `prompts/<date>-<NN>-<slug>.md`, `NN` = ordre du jour ; `id` = `<date>-<NN>`, unique.
- Un prompt commité en `ready`, `applied`, `superseded` ou `withdrawn` ne change plus que par sa ligne `status` (le lint compare à `HEAD`). Toute correction = nouveau fichier avec `supersedes: <id>`, l'ancien passe `superseded`.
- `contract` = version du cadrage (AGENTS.md, templates, policy) supposée par le prompt.
- `target` : `factory-dev`, `factory-review`, `opencode-plan` (agent `plan` intégré, lecture seule), `human`.

## Appliquer un prompt au travail

1. `git pull` de ce dépôt sur la machine de travail.
2. Prendre le plus ancien prompt `ready` non appliqué (ou celui que le mainteneur désigne).
3. Selon `target` :
   - `opencode-plan` : dans le dépôt du scanner, `opencode` avec l'agent `plan`, coller le prompt.
   - `factory-dev` : le prompt produit ou accompagne des tickets ; `fx.py start <ticket.md>` puis `opencode` dans le worktree (agent `factory-dev` par défaut).
   - `factory-review` : dans le worktree du ticket, agent `factory-review`.
4. Passer le prompt en `applied` (commit `applied: <id>`).

## Retour des résultats

- Le rapport de l'agent (format fixe) et le journal (`<journal>/<ID>/runs.jsonl` + logs) restent sur la machine de travail.
- Le mainteneur rapporte à Claude ce qu'il choisit : rapport agent, lignes de journal, résumé, après avoir retiré noms, URLs internes, secrets et code non nécessaire.
- Si le remote de ce dépôt est interne à l'entreprise, les rapports peuvent être commités sous `results/<prompt-id>/` ; sinon ils n'y vont pas.

## Mise en place côté scanner (après validation du design)

```bash
cp factory/local.example.json factory/local.json     # repo, base, sandbox, model
cp factory/gates.example.json factory/gates.json     # commandes réelles du scanner
cp AGENTS.md "$SCANNER/AGENTS.md"                    # commit dans le scanner
python3 factory/fx.py start path/to/T-123.md
```

Puis la sonde de permissions et le ticket pilote (DEV-FACTORY.md, « Mise en service »).
