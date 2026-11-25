---
# Agent contract. fx.py reads every field; flat format only. Comments need two spaces before '#'.
id: T-000
title: Short imperative title
area: output  # one module/area per ticket
type: fp-fix  # feature | fix | fp-fix | fn-fix | refactor | test | corpus | chore
status: draft  # draft -> ready (maintainer) ; fx.py start only accepts ready
allowed_paths:
  - src/scanner/output/*
  - tests/output/*
  - regression/cases/cwe-89/T-000/*  # the new case directory, exact
forbidden_paths: []
new_dependencies: []  # e.g. [ "jsonschema==4.23.0" ]; empty = no manifest change allowed
unlock: []  # exact locked paths this ticket may change: golden re-pin, conftest, pyproject...
model_eval: false  # true = live-model regression at merge (prompts, skills, model changes)
max_diff_lines: 300
attempts_max: 3
prompt: null  # id of the scanner-prompts prompt that produced this ticket
---

## Context
Two or three sentences: what is wrong or missing, where. No design beyond what the criteria need.

## Acceptance criteria
One line per criterion, each with exactly one named test in backticks. fx.py refuses a criterion without a test.

- AC-1: Given <input>, when <action>, then <observable result>. Test: `tests/output/test_x.py::test_y`

## Tests to write first
All the tests above, written before any implementation; `fx.py gates --red <test>` must print RED-OK for each.
- fp-fix: add `regression/cases/<rule>/<case-id>/clean/` + `expected.json` with no findings.
- fn-fix: add `regression/cases/<rule>/<case-id>/vulnerable/` + `expected.json` with the finding.

## Out of scope
What the agent must not change even if it looks wrong (report it under OUT OF SCOPE SEEN).

## Unlock (only if unlock is not empty)
For each path: why it changes; for a golden re-pin, why the new output is correct and who checked it.
