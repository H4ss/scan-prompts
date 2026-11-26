---
id: 2026-11-26-09
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: superseded
supersedes: null
---

# Unit retries: six corrections, then one full scan against its reference

Maintainer lines (filled when pasting):
```
REFERENCE RUN: <full scan of the target, made with the old code>
GATEWAY LIMIT: <value> ; source: <documentation | answer of its owner | observed>
FULL SCAN: <go | wait>
```

## Goal
The work on `feat/unit-retries` gave a strong result on one zone run alone. Three limits remain before it can be called a result on scans:

- one zone, chosen because it was the worst, running alone with the whole gateway for itself, is the best case;
- only one attempt happened, so no retry path has run for real yet;
- several numbers behind the design are still estimates (requests in flight, the gateway limit, the cache).

This prompt closes those gaps, corrects one design choice, then runs one full scan compared with its reference. Argue with evidence where you disagree.

## Inputs
Branch `feat/unit-retries` and its worktree, `docs/unit-retry-facts.md`, `docs/unit-retry-report.md`, the logs of `REFERENCE RUN`.

## Steps

### C1. One file per finding
Today the scan skill asks the unit to rewrite the whole findings file with a growing array each time. The model then types every earlier finding again at each write: output grows with the square of the number of findings, and an earlier finding can be altered or dropped without anyone seeing it.
- The unit writes each finding once, in its own file (`<out-dir>/findings/<n>.json`), and never touches it again.
- Python assembles the unit's findings file at the end of the unit and after any interruption.
- Test: after an interruption, the findings written before it are byte-identical. Quote the new sentence of the skill.

### C2. Request timeout
- Say whether `request_timeout_s` is a total duration or a stall (no byte received).
- From the logs of the reference runs: duration of model requests (median, p95, p99, maximum), and the same split by size of the request's context.
- If answers are streamed: use a stall timeout, and keep a total limit only as a safety net at twice the recorded maximum. If they are not: set the timeout to twice the p99, and write what one dead request then costs in minutes.

### C3. Requests in flight, measured
The count was an estimate, so the request budget cannot be checked. Record per scan: highest number of simultaneous model requests, time spent at the limit, time spent waiting for a slot. Two different values of the gateway limit appeared in two of your reports: state the one you use and where it comes from. Do not probe a shared gateway with load to find it.

### C4. Cache, one observation
Print the raw usage block of two consecutive requests of one session as the gateway returns it, before any adapter. Conclusion in one line: the gateway returns cached counts, or it does not. If it does, record them in the metrics. Nothing more in this prompt.

### C5. A resume that does not start
The facts show attempts with no step and no token that still lasted several minutes. Show the test proving this cannot happen any more: a resumed session that produces no event within `resume_start_timeout` (short) is abandoned at once and replaced by a new session from the checkpoint. It does not wait for the idle timeout. If no test covers it, add the behaviour and the test.

### C6. Housekeeping facts
- The temporary directory was full. What filled it, how much one scan leaves behind, what removes it today. Add a cleanup at the end of a scan behind a setting, and a check before a scan starts: not enough free space means the scan is refused with a clear message, not started.
- The fixes unrelated to retries made on this branch: list them, one commit each, so they can be taken separately.
- The test of sandbox hardening and mounts is red "for environment reasons". Say where it passes. If it passes nowhere, write that plainly: it is the test of the sandbox's isolation.

### F1. Prediction, written before the scan
From the facts already measured: useful agent time of the reference scan stage (its total minus the work done again), divided by the number of units allowed at once under the request budget. Write the predicted duration of the scan stage and the predicted tokens. A prediction written first keeps the comparison honest.

### F2. Full scan (only if `FULL SCAN: go`, and only when the scheduler is free)
Same target, same model and same settings as `REFERENCE RUN`, except the retry settings you recommend.
Compare with the reference, per stage: duration, tokens in and out. For the scan stage: attempts by cause, share of tokens and of time spent on work done again, highest requests in flight, time waiting for a slot, units `incomplete` with their uncovered files, effective concurrency of units.
List every cause of the retry table that really occurred and the action taken. A cause that did not occur stays "tested with fakes only" in the report.

### F3. Stability of findings, without a model
On the single zone, one finding in eight was identical and the others were called equivalent. That judgement must come from a rule. Match the findings of the new scan with those of the reference in Python:

| class | rule |
|---|---|
| same | same file, same category, overlapping lines |
| moved | same file, same category, other lines |
| same file | same file, other category |
| only in the reference | no match |
| only in the new scan | no match |

Give the counts for all findings before triage, then for the findings triage confirmed. This is also the first measure of how much two scans of the same code differ.

## Constraints
- Same branch `feat/unit-retries`, same worktree. A running scan, its worktree and its process are not touched.
- Defaults still reproduce the old behaviour; the new behaviour stays behind settings.
- No change to zone generation, triage or ranking. The only change in the scan skill is the sentence of C1.
- One commit per ticket, subject `scan: <ticket> <what>`.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: `FULL SCAN` is `wait` (do C1 to C6 and F1, then report); the unit cannot write separate files without a larger rewrite of the skill; free space is not enough for a full scan.

## Report
```
C1: sentence <quote> ; test identical after interruption <ok|ko>
C2: timeout is <stall | total> ; request duration median <n> p95 <n> p99 <n> max <n> ; value chosen <n>, because <one line>
C3: gateway limit <n>, source <...> ; requests in flight recorded <yes|no>
C4: gateway returns cached counts <yes|no>
C5: resume that does not start <covered by test <name> | added>
C6: temp dir filled by <what>, <size> per scan ; cleanup <added> ; unrelated commits <list> ; hardening test passes <where | nowhere>
F1: predicted scan stage <duration>, <tokens>
F2: scan stage <reference / new / predicted> ; triage <reference / new> ; total <reference / new> ; work done again <x % tokens, x % time> ; highest in flight <n> ; incomplete units <n> ; causes that occurred <list> ; tested with fakes only <list>
F3: before triage: same <n>, moved <n>, same file <n>, only reference <n>, only new <n> ; confirmed by triage: <same five counts>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
