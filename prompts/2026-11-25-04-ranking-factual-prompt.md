---
id: 2026-11-25-04
date: 2026-11-25
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: withdrawn
supersedes: null
---

# Ranking v2, task 2 of 3: the ranking agent states facts, the pipeline derives severity

Apply only after task 1 (`2026-11-25-03`) is DONE: `anduril/ranking.py` must exist with `normalise` and `derive_severity`.

## Goal
On branch `feat/critical-ranking`:
1. the Phase 4 ranking prompt stops asking the agent to promote to CRITICAL and asks for facts with `file:line` evidence instead;
2. those facts are written to `TRIAGE.json`;
3. after `TRIAGE.json` is validated, the pipeline computes the final severity with `anduril/ranking.py` and stores the rules that fired;
4. the reports show those rules under "Why this severity".

After this task no finding can be CRITICAL yet: a finding that meets every condition is marked `critical_candidate`. Task 3 adds the challenge pass that confirms candidates.

## Inputs
`.claude/skills/triage/SKILL.md` (Phase 4: 4a ranking prompt, 4b merge; Phase 6: output contract), `anduril/schemas/triage.schema.json`, `anduril/pipeline.py` (around `validate_triage`), `anduril/ranking.py`, `anduril/reporting/model.py` (around the `severity_rationale` extraction), `tests/test_reporting.py`, `tests/test_ranking.py`.

## Steps

### 1. Phase 4a ranking prompt
a. STEP 1: append this paragraph.
```
Prefix each precondition with its kind:
  [auth]      the access the attacker needs (also stated in REACH below)
  [config]    a non-default configuration or feature flag
  [victim]    an action by another user
  [race]      a timing window
  [knowledge] a secret or unguessable value the attacker must already know
  [chain]     a second, separate vulnerability
  [other]     anything else
Do not list "the attacker can send a request".
```
b. Replace the whole STEP 2b (the "Critical promotion" contract and the factor line instruction) with:
```
STEP 2b: Severity facts. You do not decide CRITICAL: there is no CRITICAL
in your answer. Answer the questions below from the code you re-read; the
pipeline computes the final severity from your answers. Every answer needs
file:line evidence. If you cannot find the evidence, answer `unknown`.
Never guess.

REACH: who can deliver the input that triggers the bug?
  unauth_remote  a network caller with no credentials
  auth_low       any ordinary account, including self-registration
  auth_priv      an administrator, operator or other specific role
  local          local access, CLI argument, environment, config file
  unknown        you could not establish it

AUTH_EVIDENCE: where authentication is, or would be, enforced for this
entry point. Reading the handler alone is not enough: cite the line where
the route or entry point is registered AND the line of the router group,
global middleware, decorator, filter or gateway configuration that applies
to it (or that shows none applies). If you cannot locate the registration,
REACH is `unknown` and AUTH_EVIDENCE is `none`.

IMPACT: what a successful attack gives, as shown by the sink you traced.
  full_compromise       server-side code or command execution, or an
                        authentication bypass that yields another user's
                        or an administrator's session
  secrets_or_bulk_data  read of credentials, keys or tokens, or of other
                        users' data beyond one record
  critical_asset_write  unauthorised create, change or delete of an asset
                        listed in the THREAT MODEL; name it in IMPACT_ASSET
  limited               anything smaller: one record, the caller's own
                        data, client-side effects
  availability          crash or degraded service only
  none
IMPACT_EVIDENCE: file:line of the sink and one sentence on what it gives.

PROD_PATH: yes | no. `no` if the code is in tests, fixtures, examples,
build scripts or development-only configuration.
```
c. STEP 3: restore the upstream sentence: `A match may raise severity by ONE step (LOW to MEDIUM or MEDIUM to HIGH), never two.` (remove the mention of STEP 2b).
d. STEP 6: `Otherwise set it equal to the derived HIGH/MEDIUM/LOW.`
e. Output block: `SEVERITY: <HIGH|MEDIUM|LOW>`, tagged preconditions, and the new lines, in this order after `ACCESS_LEVEL`:
```
  PRECONDITIONS:
  - [kind] <one per line, or "none">
  ACCESS_LEVEL: <unauthenticated_remote|authenticated|local|physical>
  REACH: <unauth_remote|auth_low|auth_priv|local|unknown>
  AUTH_EVIDENCE: <file:line; file:line | none>
  IMPACT: <full_compromise|secrets_or_bulk_data|critical_asset_write|limited|availability|none>
  IMPACT_ASSET: <threat-model asset name | none>
  IMPACT_EVIDENCE: <file:line + one sentence>
  PROD_PATH: <yes|no>
  SEVERITY: <HIGH|MEDIUM|LOW>
  (the remaining lines unchanged)
```

### 2. Phase 4b merge and Phase 6 output contract
- 4b: the orchestrator attaches the new values to the finding, verbatim, as `reach`, `auth_evidence`, `impact`, `impact_asset`, `impact_evidence`, `prod_path`; `preconditions` keeps the `[kind]` tags. Non-confirmed findings get `null` for the six new fields.
- 6b: add the six fields to the documented per-finding object. State that `severity` in the final file may be `CRITICAL` and is set by the pipeline, not by the ranking agent. Keep the 6a sort with CRITICAL first.

### 3. Schema
In `anduril/schemas/triage.schema.json`, add as optional per-finding properties: `reach`, `auth_evidence`, `impact`, `impact_asset`, `impact_evidence`, `prod_path` (string or null); and the pipeline-written ones: `model_severity` (string or null), `severity_trace` (array of strings), `critical_blockers` (array of strings), `critical_candidate` (boolean), `severity_inconsistent` (boolean). No enum on these: an odd value must not fail a run, `normalise` handles it.

### 4. `apply_to_triage` in `anduril/ranking.py`
```python
def apply_to_triage(doc: dict) -> dict:
    """Mutates and returns the TRIAGE.json document. Pure apart from the mutation."""
    for finding in doc["findings"]:
        if finding.get("verdict") != "true_positive":
            continue
        result = derive_severity(normalise(finding))
        if "model_severity" not in finding:              # idempotent: keep the agent's first answer
            finding["model_severity"] = finding.get("severity")
        finding["severity"]             = result["severity"]
        finding["severity_trace"]       = result["trace"]
        finding["critical_blockers"]    = result["critical_blockers"]
        finding["critical_candidate"]   = result["critical_candidate"]
        finding["severity_inconsistent"] = result["severity_inconsistent"]
    recompute doc["summary"]["by_severity"] over true positives, with a CRITICAL key
    return doc
```
Note: `normalise` must read the agent's severity from `model_severity` when that key exists, else from `severity`. Adjust `normalise` and add a test: applying twice gives the same document.

### 5. Pipeline
Right after `validate_triage` succeeds (`anduril/pipeline.py`, near the existing call): copy the validated file to `TRIAGE.model.json` next to it (the agent's untouched output, for audit), run `apply_to_triage`, write `TRIAGE.json` back, and log one line per finding whose severity changed: id, model severity, final severity, the trace. If `apply_to_triage` raises, keep the original `TRIAGE.json`, log the error, and let the run continue.

### 6. Reporting
In `anduril/reporting/model.py`, where `severity_rationale` is built: when the finding has a non-empty `severity_trace`, set `severity_rationale` to the trace lines joined with `"; "`, followed, when the final severity is HIGH and `critical_blockers` is non-empty, by `". Not CRITICAL because: " + ", ".join(critical_blockers)`. Otherwise keep today's behaviour (last paragraph of the rationale). Markdown, HTML and SARIF already display `severity_rationale`: no change there.

### 7. Tests
- `tests/test_ranking.py`: `apply_to_triage` on a small fixture document (one false positive left untouched; one true positive demoted; one lifted by F1; one candidate; idempotence; `summary.by_severity` recomputed).
- `tests/test_reporting.py`: a finding with `severity_trace` and blockers renders "Not CRITICAL because"; a finding without `severity_trace` renders as before.
- `CriticalPromotion` (3 existing tests): update their fixture so the CRITICAL finding carries `severity_trace` ending with `C2: challenge survived` instead of the factor line, and assert on the trace text. These three tests are the only existing tests you may edit.

### 8. Do not run a scan
Give the exact command that re-runs triage on an existing run without re-scanning, and the `--stats` command to run before and after. The maintainer runs them.

## Constraints
- Only the files named in Inputs.
- `.claude/skills/vuln-scan/SKILL.md` is not changed: the scanner still claims HIGH, MEDIUM or LOW.
- No new dependency. No network. No scan or triage run.
- Apart from the three `CriticalPromotion` tests, existing tests are not modified, skipped or deleted.
- One commit, subject `ranking-v2 T2: factual ranking prompt and derived severity`.

## Stop conditions
Stop and report BLOCKED when: task 1 is missing; `validate_triage` or the `severity_rationale` code is not where this prompt says and there is no obvious equivalent; the schema forbids additional properties in a way that needs a wider change; an unrelated test fails; three failed attempts at making the tests pass.

## Report
```
TASK: T2
STATUS: DONE | BLOCKED
TESTS: <command> -> <passed>/<total>
FILES: <path> (+added/-deleted), ...
DEVIATIONS: <where you departed from this prompt and why, or none>
BLOCKERS: <what is needed, or none>
RE-TRIAGE COMMAND: <exact command, not run>
STATS COMMAND: <exact command, not run>
```
