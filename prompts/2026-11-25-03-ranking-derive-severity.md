---
id: 2026-11-25-03
date: 2026-11-25
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: withdrawn
supersedes: null
---

# Ranking v2, task 1 of 3: `derive_severity`, a pure function, and its tests

## Goal
Add `anduril/ranking.py`: pure functions that compute a finding's severity from facts stored in `TRIAGE.json`, and record which rules fired. This task changes no prompt, no pipeline step and no report: nothing calls the new module yet. Branch: `feat/critical-ranking`.

Why: today the ranking agent decides the severity, CRITICAL included, in free text that no code checks. After the three tasks, the agent will state facts with evidence and this module will derive the severity, so every result can be explained by a list of rules.

## Inputs
`anduril/schemas/triage.schema.json` and one existing `TRIAGE.json` (to see the field names), `tests/` (to follow the existing test style). Nothing else.

## Steps

1. Write `tests/test_ranking.py` first, from the tables below. Run it, see it fail.
2. Implement `anduril/ranking.py`. No I/O in `normalise` and `derive_severity`, no model call, no global state, standard library only.
3. Add the `--stats` command line (step 6 below).
4. Run the whole test suite.

### Vocabulary

```python
ORDER   = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
REACH   = {"unauth_remote", "auth_low", "auth_priv", "local", "unknown"}
IMPACT  = {"full_compromise", "secrets_or_bulk_data", "critical_asset_write",
           "limited", "availability", "none"}
TIER_A  = {"full_compromise", "secrets_or_bulk_data", "critical_asset_write"}
COUNTED = {"config", "victim", "race", "knowledge", "chain", "other"}   # precondition kinds that count
# kind "auth" exists but is NOT counted: the access level is carried by `reach`.
```

### `normalise(finding: dict) -> dict`
Tolerant read of one finding of `TRIAGE.json`. Never raises on missing or odd values.

| output key | source | rule |
|---|---|---|
| `reach` | `finding["reach"]` | lower-case, strip; if not in `REACH`, fall back to the legacy `access_level`: `unauthenticated_remote` → `unauth_remote`, `authenticated` → `auth_priv`, `local` or `physical` → `local`, anything else → `unknown` |
| `auth_evidence` | `finding["auth_evidence"]` | string; `""` if missing, `none` or `null` |
| `impact` | `finding["impact"]` | lower-case; `none` if missing or not in `IMPACT` |
| `impact_asset` | `finding["impact_asset"]` | string; `""` if missing or `none` |
| `preconditions` | `finding["preconditions"]` (list of strings) | each item `"[kind] text"` → `{kind, text}`; no tag or unknown tag → kind `other`; an item equal to `none` (any case) is dropped |
| `prod_path` | `finding["prod_path"]` | `yes` or `no`; `no` if missing or anything else |
| `verify_verdict` | `finding["verify_verdict"]` | as is, `""` if missing |
| `votes` | `finding["vote_breakdown"]` | `{true_positive, total}` with `total` = sum of the three counters; `{0, 0}` if missing |
| `threat_match` | `finding["threat_match"]` | string; `""` if missing, `none` or `null` |
| `model_severity` | `finding["severity"]` | upper-case, as the agent wrote it |
| `challenge` | `finding["challenge"]["result"]` | `survived`, `refuted` or `None` |

### `derive_severity(f: dict) -> dict`
`f` is the output of `normalise`. Returns `{severity, trace, critical_blockers, critical_candidate, severity_inconsistent}`.

```python
def table_severity(n_pre, reach):                                   # rule T2
    by_count = "HIGH" if n_pre == 0 else "MEDIUM" if n_pre <= 2 else "LOW"
    by_reach = {"unauth_remote": "HIGH", "auth_low": "MEDIUM", "auth_priv": "MEDIUM",
                "unknown": "MEDIUM", "local": "LOW"}[reach]
    return lower_of(by_count, by_reach)

def derive_severity(f):
    trace, blockers, candidate = [], [], False
    n_pre = number of preconditions whose kind is in COUNTED
    sev = table_severity(n_pre, f["reach"])
    trace.append(f"T2: {n_pre} precondition(s) + {f['reach']} = {sev}")

    # rule F1: any ordinary account, nothing else needed, major impact -> at least HIGH
    if f["reach"] == "auth_low" and n_pre == 0 and f["impact"] in TIER_A and sev is below HIGH:
        sev = "HIGH"
        trace.append(f"F1: ordinary account, no precondition, impact {f['impact']} = HIGH")

    # rule T3: threat-model match raises by one step, never above HIGH
    if f["threat_match"] and sev is below HIGH:
        sev = one step up
        trace.append(f"T3: threat model match = {sev}")

    # rule C1: conditions for CRITICAL, evaluated on every HIGH
    if sev == "HIGH":
        checks = [                       # (label, holds) in this order
            ("reach=unauth_remote",        f["reach"] == "unauth_remote"),
            ("auth evidence present",      f["auth_evidence"] != ""),
            ("no precondition",            n_pre == 0),
            ("impact in tier A",           f["impact"] in TIER_A),
            ("critical asset named",       f["impact"] != "critical_asset_write" or f["impact_asset"] != ""),
            ("production code path",       f["prod_path"] == "yes"),
            ("verify_verdict=exploitable", f["verify_verdict"] == "exploitable"),
            ("no dissenting vote",         f["votes"]["total"] >= 1
                                           and f["votes"]["true_positive"] == f["votes"]["total"]),
        ]
        blockers = [label for label, holds in checks if not holds]
        if not blockers:
            if f["challenge"] == "survived":                        # rule C2
                sev = "CRITICAL"
                trace += ["C1: all critical conditions hold", "C2: challenge survived"]
            elif f["challenge"] == "refuted":
                blockers = ["challenge refuted a factor"]
                trace.append("C2: challenge refuted, stays HIGH")
            else:
                candidate = True
                trace.append("C1: all critical conditions hold, challenge pending")

    # what the agent should have written by applying STEP 2 and STEP 3 itself (no F1, no CRITICAL)
    baseline = table_severity(n_pre, f["reach"])
    if f["threat_match"] and baseline is below HIGH:
        baseline = one step up
    inconsistent = f["model_severity"] in ("HIGH", "MEDIUM", "LOW") and f["model_severity"] != baseline
    return {"severity": sev, "trace": trace, "critical_blockers": blockers,
            "critical_candidate": candidate, "severity_inconsistent": inconsistent}
```

### Test table for `derive_severity`
One test per row. `pre` = number of counted preconditions. Unless the row says otherwise: `auth_evidence` set, `prod_path=yes`, `verify_verdict=exploitable`, votes 1 true positive out of 1, no threat match, `challenge=None`.

| # | reach | pre | impact | other | severity | must appear |
|---|---|---|---|---|---|---|
| 1 | unauth_remote | 0 | full_compromise | challenge=survived | CRITICAL | trace has C1 and C2 |
| 2 | unauth_remote | 0 | full_compromise | | HIGH | candidate is True |
| 3 | unauth_remote | 0 | full_compromise | challenge=refuted | HIGH | blocker "challenge refuted a factor" |
| 4 | unauth_remote | 0 | limited | | HIGH | blocker "impact in tier A" |
| 5 | unauth_remote | 0 | secrets_or_bulk_data | votes 2 of 3 | HIGH | blocker "no dissenting vote" |
| 6 | unauth_remote | 0 | full_compromise | verify_verdict=needs_manual_test, challenge=survived | HIGH | blocker "verify_verdict=exploitable" |
| 7 | unauth_remote | 0 | full_compromise | auth_evidence empty | HIGH | blocker "auth evidence present" |
| 8 | unauth_remote | 0 | full_compromise | prod_path=no | HIGH | blocker "production code path" |
| 9 | unauth_remote | 1 | full_compromise | | MEDIUM | trace is T2 only |
| 10 | auth_low | 0 | full_compromise | | HIGH | trace has F1; blocker "reach=unauth_remote" |
| 11 | auth_low | 0 | limited | | MEDIUM | trace is T2 only |
| 12 | auth_low | 0 | limited | threat_match set | HIGH | trace has T3; blockers reach and impact |
| 13 | auth_priv | 0 | full_compromise | | MEDIUM | no F1 |
| 14 | local | 0 | full_compromise | threat_match set | MEDIUM | trace has T3 |
| 15 | unknown | 0 | full_compromise | | MEDIUM | trace is T2 only |
| 16 | unauth_remote | 3 | full_compromise | | LOW | trace is T2 only |
| 17 | unauth_remote | 0 | critical_asset_write | impact_asset empty | HIGH | blocker "critical asset named" |
| 18 | unauth_remote | 0 | critical_asset_write | impact_asset set, challenge=survived | CRITICAL | |
| 19 | unauth_remote | 1 | full_compromise | threat_match set | HIGH | trace has T3; blocker "no precondition" |
| 20 | unauth_remote | 0 | full_compromise | one precondition of kind `auth` only | HIGH | candidate is True (kind auth is not counted) |

Property test: loop over every combination of `reach`, `impact`, `pre` in 0..3, `prod_path`, `verify_verdict` in (`exploitable`, `mitigated`, `needs_manual_test`), `challenge` in (`None`, `survived`, `refuted`), threat match set or not. Assert: the result is CRITICAL only when `challenge == "survived"` and `reach == "unauth_remote"` and `pre == 0` and `verify_verdict == "exploitable"`.

### Tests for `normalise`
- a legacy finding (only `access_level: authenticated`, untagged preconditions) → `reach=auth_priv`, every precondition of kind `other`;
- tags: `"[config] flag X on"`, `"[auth] needs a session"`, `"[weird] x"`, `"no tag"`, `"none"` → kinds `config`, `auth`, `other`, `other`, and the last one dropped;
- missing fields → the defaults of the table above, no exception;
- `reach: "UNAUTH_REMOTE "` → `unauth_remote`; `impact: "rce"` → `none`.

### Step 6: command line
`python -m anduril.ranking --stats <path/to/TRIAGE.json>` prints counts only, no finding text:
- confirmed findings by `severity` as stored in the file, and by computed severity;
- how many differ; how many have `severity_inconsistent`;
- how many traces contain F1, T3, C1;
- a histogram of `critical_blockers` labels.

## Constraints
- New files only: `anduril/ranking.py`, `tests/test_ranking.py`. No other file changes.
- No new dependency. No network. No scan run.
- Existing tests are not modified.
- Commit subject: `ranking-v2 T1: derive_severity and tests`.

## Stop conditions
Stop and report BLOCKED when: a field name in the real `TRIAGE.json` contradicts this prompt; an existing test fails for a reason unrelated to this task; three failed attempts at making the new tests pass.

## Report
```
TASK: T1
STATUS: DONE | BLOCKED
TESTS: <command> -> <passed>/<total>
FILES: <path> (+added/-deleted), ...
DEVIATIONS: <where you departed from this prompt and why, or none>
BLOCKERS: <what is needed, or none>
STATS COMMAND: <the exact command the maintainer can run on an existing TRIAGE.json>
```
