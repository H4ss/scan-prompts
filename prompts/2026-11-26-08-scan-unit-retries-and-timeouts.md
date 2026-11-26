---
id: 2026-11-26-08
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: applied
supersedes: null
---

# Scan units: retries that do not redo the work, timeouts that look at the right signal

Maintainer lines (filled when pasting):
```
DEV BRANCH: <branch to start from>
GATEWAY LIMIT: <maximum concurrent model requests the gateway accepts>
REFERENCE RUNS: <1 to 3 finished runs to measure>
ZONE TO RERUN: <run and unit with the most attempts>
```

## Goal
Your analysis of the last runs: half of the scan units need three or four attempts; each retry resumes the session and pays the whole context again; units and their sub-agents together ask the gateway for more requests than it accepts, sub-agents get killed, the parent waits in silence, the idle timer takes that silence for a hang and starts the next attempt, which meets the same wall. Scan time then follows the retries and the slowest unit, not the size of the code.

A longer idle timer is not the fix: it is the same blind timer, later. The fix has four parts:

1. the timer watches the whole session tree and the requests in flight, not the parent's output;
2. the scan never asks the gateway for more than it accepts: a request waits instead of failing;
3. a failure is classified before anything is retried, and each cause has its own action;
4. a new attempt starts from a checkpoint and does not replay the old conversation.

Every behaviour is a setting whose default keeps today's behaviour. Argue with evidence where you disagree.

## Inputs
The unit runner (start, watch, retry, resume), the scan skill, the settings file, the session and gateway logs of `REFERENCE RUNS`, `run_metrics.json`, your retry and zone-size tickets.

## Steps

### T1. Facts (read-only, first) in `docs/unit-retry-facts.md`
Measures come from logs. An estimate is marked `estimate`.

a. **Per unit** of each reference run: zone size (files, lines); number of attempts; per attempt: duration, tokens in and out, how it ended, last event before the end, findings written before and after. Then per run: share of scan tokens and of scan time spent in attempts whose work was done again.

b. **The mechanism as the code has it**, with file and line: what is watched to call a unit idle; what a retry does exactly (resume or new session, what is sent again); what counts as an attempt; what becomes of findings already found when a unit fails for good; how sub-agents are started and how many at once; where a gateway refusal shows up and who then kills what; the current value of every timeout and limit.

c. **Requests in flight**: the highest number of simultaneous model requests during the scan against `GATEWAY LIMIT`; number of refusals by the gateway, per unit.

d. **Cache**: cached input tokens are zero everywhere. Find which is true: the gateway offers no cache; it offers one but something changes at the start of each request (a date, a run id, an unstable order of tools or files); it works but is not recorded. Show the usage block of two consecutive turns of one session. If the cause is on our side, say what would fix it; do not fix it in this prompt.

e. **Findings**: does a unit write its findings as it goes, or only at the end?

f. **Size**: one table of units sorted by lines, with duration, attempts and tokens. Does a bigger zone mean more attempts?

### T2. Liveness
- A unit is alive while anything in its session tree is active: the parent or any sub-agent produced an event, or a model request is in flight, including one waiting for a slot (T3). The unit is idle only when nothing in the tree happened for `stages.scan.idle_timeout`.
- A single model request gets a stall timeout: no byte received for `request_stall_timeout`. A stalled request is retried as a request; the session is not restarted.
- When a unit is stopped, the cause is recorded with the last event of each session of its tree.

### T3. Request budget
- Requirement: the model requests in flight for a whole scan never exceed `GATEWAY LIMIT`. A request above the limit waits; it does not fail, and waiting counts as alive.
- Choose the mechanism the runtime allows and justify it: (a) one limiter that every session of the scan goes through; (b) a static budget, `running units × (1 + sub-agents per unit) ≤ GATEWAY LIMIT`, refused at load time when exceeded. If (a) needs a component you cannot add safely, do (b).
- A refusal by the gateway is retried as a request, after a wait that grows and is randomised, and that follows the delay the gateway asks for when it gives one. It never counts as an attempt of the unit.
- Optional, behind `adaptive_units: on|off`: several refusals within a minute lower the number of running units by one, until a quiet period brings it back.

### T4. One action per cause

| cause | how it is recognised | action | counts as an attempt |
|---|---|---|---|
| refused by the gateway | rate-limit or overload answer | wait, send the request again | no |
| request stalled | no byte for the stall timeout | send the request again, 3 times at most | no |
| sub-agent ended without result | child session gone, no answer | the parent receives an error result and goes on; the child is started again once | no |
| idle | nothing in the tree for the idle timeout | resume once, with a short message saying what was pending | yes |
| wedged | idle again at the same last event | no resume: new session from the checkpoint (T5) | yes |
| context full | window exceeded | no resume: new session from the checkpoint, on what is left | yes |
| token budget passed | unit above `unit_token_budget` | stop, unit `incomplete` | final |
| sandbox or tool failure | error outside the model | new session from the checkpoint, once | yes |

At most `max_attempts` (default: today's value). After the last one the unit is `incomplete`: its findings are kept, and `COVERAGE.json` lists the files it did not cover. A unit never ends with nothing when it had found something.

### T5. Checkpoint
- Progress is derived by Python from the session's own tool calls (files read, searches done), not declared by the model.
- Findings reach the zone's result file as soon as each one is established. If T1e says they are written only at the end, change the scan skill by the smallest wording possible and quote the sentence changed.
- A new session from the checkpoint receives: the zone brief, the files already covered, one line per finding already written, and the instruction not to redo them. It does not receive the old conversation. The cost of a new attempt no longer grows with the length of the failed one.

### T6. Order and budget
- `stages.scan.order: as_generated | size_desc`. With `size_desc` the largest zones start first, so the last wave is made of small units.
- `stages.scan.unit_token_budget`: off by default. The metrics always flag a unit above twice the median of its run.

### T7. Metrics
`run_metrics.json`, per unit: attempts with their cause, tokens per attempt, tokens of work done again, time spent waiting for a slot, state (`complete`, `incomplete`). Per scan: highest number of requests in flight, refusals, share of tokens and of time spent on work done again, effective concurrency of units (sum of unit durations / scan wall-clock).

### T8. Tests
- **Without a model**: a local stub in place of the gateway (refuses, stalls, answers slowly) and a fake session. One test per row of T4, plus: a silent parent with a working child is not stopped; the budget of T3 is never exceeded; a new session from a checkpoint does not receive the old conversation.
- **One real zone**, only when the scheduler is free: run `ZONE TO RERUN` alone, with the zone definition stored by its run, with the new settings on. Compare with what that unit recorded: attempts and their causes, tokens, duration, findings.
- **One full scan**: only on the maintainer's go, compared with the same target in `REFERENCE RUNS`.

Accepted when, on the real zone: no attempt was caused by silence while a child was working; no refusal consumed an attempt; tokens are not above the recorded ones; no finding of the record is missing without an explanation. On the full scan: requests in flight stay under the limit; work done again is under 5 % of scan tokens; every `incomplete` unit lists its uncovered files.

## Constraints
- New branch `feat/unit-retries` in its own worktree, from `DEV BRANCH`. A running scan, its worktree and its process are not touched.
- Defaults reproduce today's behaviour. Give, at the end, the settings you recommend for the next scan.
- No change to zone generation, triage or ranking. The only change allowed in the scan skill is the one of T5.
- Raising the idle timeout alone is not an accepted result.
- One commit per ticket, subject `scan: <ticket> <what>`.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: the runner cannot see the sub-agents of a unit or the requests in flight; neither mechanism of T3 is possible; a new session from a checkpoint would need a rewrite of the scan skill beyond one sentence.

## Report
```
T1: units with more than one attempt <n of total> ; work done again <x % of tokens, x % of time> ; highest requests in flight <n> for a limit of <n> ; refusals <n> ; cache <no cache | broken by <what> | not recorded> ; findings written <as it goes | at the end> ; bigger zone means more attempts <yes | no>
T2-T5: tests <passed/total> ; mechanism chosen for T3 <a | b>, because <one line> ; sentence changed in the scan skill <quote, or none>
REAL ZONE: attempts <recorded / new> ; tokens <recorded / new> ; duration <recorded / new> ; findings <recorded / new, missing n>
SETTINGS FOR THE NEXT SCAN: <list>
NOT DONE: <tickets or parts, with the reason>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
