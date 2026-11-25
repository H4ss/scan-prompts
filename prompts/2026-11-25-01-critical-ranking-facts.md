---
id: 2026-11-25-01
date: 2026-11-25
version: 1
contract: "0.2"
target: opencode-plan
tickets: []
status: ready
supersedes: null
---

# Critical ranking: facts needed before the v2 change (read-only)

## Goal
Give exact facts about how severity is produced today on branch `feat/critical-ranking`, from the scan claim to the report. The answers decide the design of the next change. Facts only, each with evidence (`path:line`, or a short verbatim quote). Write `unknown` when the code does not tell. Do not propose changes.

## Inputs
The anduril repository on branch `feat/critical-ranking`, read-only: `.claude/skills/vuln-scan/SKILL.md`, `.claude/skills/triage/SKILL.md`, `anduril/reporting/`, `docs/ranking.md`, `tests/test_reporting.py`, the code that runs the triage phases and parses their output, and the andurilctl code that merges results.

## Steps
1. Phase 4 ranking prompt: paste it verbatim and complete, from its first line to the end of the output block (all STEPs, the STEP 2 table, STEP 2b, the block the agent must return).
2. Phase 4 execution: how many agents rank one finding; which inputs each receives (Phase 3 rationale, votes, threat model, environment); if more than one, how their outputs are merged into one severity and one verdict. Which model runs triage, and is it the same as the scan model.
3. Phase 3 votes: default number of verifiers per finding; where `vote_breakdown` and `confidence` are stored; the noise-tolerance setting used in normal runs (`precision`, `recall` or `ask`) and what happens to a split vote.
4. Ranking output parser: where the Phase 4 block is parsed; what happens on an invalid value (unknown SEVERITY, missing field, CRITICAL with no factor line); any validation between the model output and `TRIAGE.json`.
5. `TRIAGE.json` on this branch: every per-finding field with its type and allowed values; which fields the branch added or changed compared to the base branch.
6. Reporting model: around `anduril/reporting/model.py:565`, quote the code that computes the final severity; list every status value and which severity each one gets; quote the code that extracts `severity_rationale` from the rationale, and say what it returns when the factor line is absent or malformed.
7. SARIF writer: for one result, which fields carry severity (`level`, `properties.security-severity`, others); whether `partialFingerprints` or `fingerprints` are emitted and from what; the rule id scheme.
8. Threat model: the structure of the threat model given to the ranking prompt (section names); whether it names assets with a criticality level; quote two entries with any internal name replaced by `<redacted>`.
9. Scan output: every field of one scanner finding on this branch; whether the scanner records the entry point or the authentication state it observed.
10. Tests: names of the tests under `tests/test_reporting.py::CriticalPromotion` and one sentence on what each asserts; any fixture `TRIAGE.json` used.
11. Orchestrator: how andurilctl merges findings from several scanner runs; any minimum-severity filter or sort option; where severity is read.
12. Numbers from the most recent run on this branch, if results exist locally (counts only, no finding text): findings by claimed severity; by final severity; how many changed; how many CRITICAL; how many `needs_manual_test`.

## Constraints
- Read-only: no edits, no commits, no network, no scan run, no test run.
- Replace any company name, application name, person name, hostname, URL or credential with `<redacted>`. Finding titles and code from scanned applications must not appear.
- The output stays on the work machine until the maintainer has reviewed it.

## Stop conditions
Stop when each of the 12 sections has content or `unknown`. Stop early and say why if the branch is missing or a step would need a scan, a test run or the network.

## Report
Markdown, exactly these headings, evidence as `path:line`:
```
# Critical ranking facts — <date> — <commit sha of the branch tip>
## 1. Phase 4 ranking prompt (verbatim)
## 2. Phase 4 execution
## 3. Phase 3 votes
## 4. Ranking output parser
## 5. TRIAGE.json fields
## 6. Reporting model
## 7. SARIF
## 8. Threat model structure
## 9. Scan output fields
## 10. Tests
## 11. Orchestrator
## 12. Numbers
## Unknowns
```
