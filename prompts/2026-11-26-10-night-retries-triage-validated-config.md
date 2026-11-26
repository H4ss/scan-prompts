---
id: 2026-11-26-10
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: ready
supersedes: 2026-11-26-09
---

# Tonight: finish the retry work, find the sub-agent cap, test parallel triage, then a night of scans that survives a failure

Maintainer lines (filled when pasting):
```
TARGET A: <smaller target> ; REFERENCE RUN A: <full scan made with the old code>
TARGET B: <larger target> ; REFERENCE RUN B: <full scan made with the old code>
LYNCEUS REPORT A: <path, or none> ; LYNCEUS REPORT B: <path, or none>
NOT AFTER: <time after which no new night step starts>
```

## Goal
Three phases, in this order. Phases 1 and 2 end with a report and a stop: the maintainer validates the configuration, answers `GO`, and only then the night starts.

1. **Build and read logs** (no scan): corrections of the retry work, facts about the gateway from existing logs, parallel triage batches behind a setting, triage replay.
2. **Two short real tests**: the cap of sub-agents per scan unit, and a rehearsal of the whole night chain on a small scope.
3. **The night**: full scans and triage replays, most valuable first, each step independent of the failure of another.

Decisions already taken by the maintainer, not open for change tonight:
- scan runs **6 units at once**, as today. Nothing may make the scan do less than it does now;
- the owners of the gateway cannot be asked. Its limit is deduced from logs and from real work, never by sending artificial load;
- if triage batches run in parallel: **3 batches at once, 4 sub-agents each**, so the total stays at 12 sub-agents as today.

Argue with evidence where you disagree on anything else.

## Inputs
Branch `feat/unit-retries` and its worktree, `docs/unit-retry-facts.md`, `docs/unit-retry-report.md`, the logs of the reference runs, the triage skill and code, the existing batch launcher, the settings file.

## Steps

## Phase 1 — build and read logs

Work on a new branch `feat/night-2` created from `feat/unit-retries`, in its own worktree. One commit per ticket, subject `<area>: <ticket> <what>`.

### A1. One file per finding
The scan skill asks the unit to rewrite the whole findings file with a growing array at each finding. The model then types every earlier finding again each time: output grows with the square of the number of findings, and an earlier finding can be altered or dropped unseen.
- The unit writes each finding once, in its own file (`<out-dir>/findings/<n>.json`), and never touches it again. Python assembles the unit's findings file at the end of the unit and after any interruption.
- Test: after an interruption, findings written before it are byte-identical. Quote the new sentence of the skill.

### A2. A resume that does not start
The facts show attempts with no step and no token that lasted minutes. A resumed session that produces no event within `resume_start_timeout` (short) is abandoned at once and replaced by a new session from the checkpoint; it does not wait for the idle timeout. Show the test that covers it, or add the behaviour and the test.

### A3. Request timeout
Say whether `request_timeout_s` is a total duration or a stall (no byte received). From the logs: duration of model requests (median, p95, p99, maximum), split by size of the request's context. If answers are streamed, use a stall timeout and keep a total limit only as a safety net at twice the recorded maximum. If not, set the timeout to twice the p99 and write what one dead request then costs in minutes.

### A4. Requests in flight, recorded
Record per scan and per stage: highest number of simultaneous model requests, time spent at that level, refusals with the number in flight at that moment.

### A5. Cache, one observation
Print the raw usage block of two consecutive requests of one session as the gateway returns it, before any adapter. One line: the gateway returns cached counts, or not. If it does, record them. Nothing more.

### A6. Disk and housekeeping
- The temporary directory was full: what filled it, how much one scan leaves behind, what removes it. Add a cleanup at the end of each scan behind a setting, and a check before each scan: not enough free space means the scan is refused with a clear message.
- List the fixes unrelated to retries made on `feat/unit-retries`, one commit each.
- The test of sandbox hardening and mounts is red "for environment reasons": say where it passes. If nowhere, write it plainly; it is the test of the sandbox's isolation.

### A7. What the logs say about the gateway (read-only)
For the two reference runs, scan stage and triage stage apart:
- Are the start and the end of each model request in the logs? If yes, rebuild the number of requests in flight over time. Table per level of requests in flight: time spent there, requests completed per minute, output tokens per second in total, median request duration for requests of similar context size, refusals.
- Triage is a known point: one batch runs its coordinator and up to 12 sub-agents. How did the gateway behave at that level?
- Per scan unit: how many sub-agents were alive at the same time (median, maximum).
- Conclusion in two lines: the highest level seen without refusal; the level above which completed work per minute stops growing, or `not visible in these logs`.

### A8. Triage: what can run in parallel, and the replay
- **Table per phase of the triage skill**: who does it (coordinator, sub-agents, Python); serial or parallel today; can it overlap with the same phase of another batch; if not, why.
- **Duplicates between two batches**: how are they found today? If only inside a batch, say so.
- **From the logs, per batch**: `C` = time with no verifier and no ranker running (the coordinator works alone), `V` = the rest. With 3 batches at once and 4 sub-agents each, verification goes at the same total pace, and only the coordinators overlap: predicted gain = `(C + V) / (C/3 + V)`. Write the predicted gain before any test.
- **Do triage sessions use the unit runner and its new retry policy** (whole-tree liveness, resume start timeout)? If not, say what protects a triage batch from the failures found on scan units.
- **Replay command**: triage alone on the findings stored by a finished run, into a new directory, without scanning: `--from-run <dir> --out <dir>`, overrides for the triage settings, `--sample <n> --seed <n>` for a fixed subset. Same revision of the target as the source run. The source run is never modified (checksum before and after).
- **Setting `stages.triage.batch_parallelism`** (default 1, today's behaviour) with the number of sub-agents per batch as a setting. A failed batch is retried once, then its findings are `untriaged`. Results merge in batch order, independent of which batch ended first. An exception in a worker fails its batch with its number in the log; the pool never swallows it. Metrics per batch: start, end, `C`, `V`, calls, failures. Unit tests with a fake verifier.

## Phase 2 — two short real tests (scheduler free)

### B1. Cap of sub-agents per scan unit
Six units at once is fixed. The unknown is how many sub-agents each may run.
- Take the 6 largest zones of `REFERENCE RUN A`, with their stored definitions, all started together, new retry settings on.
- Run 1: at most 2 sub-agents per unit. Run 2: at most 4. If A7 shows that units never go above some number, adapt the two values and say why. 30 minutes at most per run; a run that passes it is stopped and recorded as such.
- Per run: wall-clock, sum of unit durations, tokens, highest requests in flight and time at that level, refusals, request duration (median, p95), attempts by cause, findings.
- Proposal: the cap that gives the shorter wall-clock without a refusal consuming an attempt and without an attempt caused by slow requests. Equal within 10 %: the lower cap.

### B2. Rehearsal of the night chain
The night must not fail on a transition nobody has run. Run the whole chain once, small, through the launcher that will run the night, started detached from your session:
1. scan of one zone of TARGET A, end to end, with the night's settings;
2. triage replay on a subset of 15 findings of `REFERENCE RUN A` with batches of 5, 3 at once, 4 sub-agents each;
3. the same replay, one batch at a time;
4. the morning report generated from these three steps.

During the rehearsal, prove each point with command output:
- the launcher survives the end of your session;
- kill the launcher once: a restart wrapper of a few lines (in the night's folder, not a new tool) starts it again, it resumes, and no step is submitted twice;
- a step that exits in failure is marked `failed` with its reason, and the next step starts;
- the free-space check runs before each step, and the cleanup after;
- one status command prints, on one screen: each step and its state, the running step with its stage and since when, the last log line, the restarts, the free space.

### Stop here
Print the `PHASE REPORT` below and wait. The night starts only when the maintainer answers `GO`, with the configuration as proposed or changed.

## Phase 3 — the night (after `GO`)

Freeze the code: tag `night-2` on `feat/night-2`; no edit of code or settings in that worktree until the morning report is written.

Settings of every scan: 6 units at once; sub-agents per unit as validated; whole-tree liveness, retry policy by cause, checkpoint, largest zones first; no automatic lowering of the number of units; threat model, gap-fill, challenge and votes as in the reference runs; triage in batches one at a time with 12 sub-agents, as today.

| step | what | answers |
|---|---|---|
| `S1` | full scan of TARGET A | the retry work on a whole scan, against `REFERENCE RUN A` |
| `R1` | replay of the triage of `S1`, 3 batches at once, 4 sub-agents each | time gained by parallel batches, against the triage of `S1` itself |
| `R2` | replay of the triage of `S1`, same settings as `S1` | noise of triage: without it the verdict changes of `R1` cannot be judged |
| `S2` | full scan of TARGET B | does the result hold on a target twice as large, against `REFERENCE RUN B` |
| `S3` | second full scan of TARGET A, same settings as `S1` | how much two scans of the same code differ |

Rules of the chain:
- One step at a time. A replay never runs during a scan.
- Before the first step, write the predicted duration of each step (for the scan stage: useful agent time of the reference divided by the units allowed at once). Drop steps from the end if the total passes `NOT AFTER`. No step starts after `NOT AFTER`.
- A step has a time limit of twice its prediction. Past it, the step is stopped, marked `failed: time limit`, and the next one starts. `R1` and `R2` need the findings of `S1`: if `S1` failed before triage, they are skipped and the chain goes on with `S2`.
- Each scan must prove its settings: once zone generation is done, the resolved settings are compared with this table by the launcher; a difference marks the step `failed: settings` and the chain goes on.
- **Stay on watch at the start.** The maintainer leaves only after you have shown: `S1` past zone generation, 6 units running, resolved settings matching, requests in flight being recorded, free space sufficient for the night.

**When the maintainer writes `status` during the night:** run the status command and show its screen. If the launcher and its wrapper are both gone, start them again through the resume path. If a step is stuck past its limit, mark it failed and let the chain go on. Never edit code or settings, never re-submit a step that ran, never start a scan outside the chain. Then say in three lines what happened since the last status.

### Morning report `reports/night-2/REPORT.md`, generated by a script from the run outputs
Most important first:
1. **Status**: each step, its state, its duration against the prediction.
2. **Retries** (`S1`, `S2` against their references), per stage: duration, tokens. Scan stage: attempts by cause, share of tokens and of time spent on work done again, highest requests in flight, `incomplete` units with their uncovered files, effective concurrency of units (sum of unit durations / wall-clock). Causes of the retry table that really occurred, and those still tested with fakes only.
3. **Parallel triage** (`R1` against the triage of `S1`): wall-clock, gain against the gain predicted in A8, `C` and `V`, refusals, `untriaged`; share of verdicts and severities changed in `R1`, next to the same share for `R2`.
4. **Stability** (`S1` against `S3`, and each against the reference), matched by this rule and never by a model's judgement:

| class | rule |
|---|---|
| same | same file, same category, overlapping lines |
| moved | same file, same category, other lines |
| same file | same file, other category |
| only in one | no match |

Counts before triage, then for findings confirmed by triage.
5. **Coverage against lynceus**, if the lynceus report lines are filled, with the existing comparison tool: `S1`, `S3`, the union of `S1` and `S3`, `S2`. The union says whether a second pass finds what the first one missed.
6. **What failed**, with the reason of each failed step, and the commands to run again what is missing.

## Constraints
- A running scan that is not part of this work, its worktree and its process are not touched.
- Defaults of every new setting reproduce the old behaviour.
- No change to zone generation or ranking. The only change in the scan skill is the sentence of A1. The triage skill's wording does not change.
- No artificial load on the gateway: every test is real work.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: the end of phase 2 is reached (always); the unit cannot write one file per finding without a larger rewrite of the skill; the launcher cannot run a replay as a step; free space is not enough for the night; the rehearsal fails on a point you cannot fix without changing the scan or triage behaviour.

## Report
At the end of phase 2:
```
PHASE REPORT
A1: sentence <quote> ; identical after interruption <ok|ko>
A2: resume that does not start <covered by <test> | added>
A3: timeout is <stall | total> ; request duration median <n> p95 <n> p99 <n> max <n> ; value <n>
A4: requests in flight recorded <yes|no>
A5: gateway returns cached counts <yes|no>
A6: temp dir filled by <what>, <size> per scan ; cleanup and check <added> ; hardening test passes <where | nowhere>
A7: highest level without refusal <n> ; work per minute stops growing at <n | not visible> ; sub-agents alive per unit median <n> max <n>
A8: phases that can overlap <list> ; cannot <list, why> ; duplicates between batches <how> ; C <x %> V <x %> ; predicted gain <x> ; triage uses the new retry policy <yes | no, protected by ...> ; tests <passed/total>
B1: cap 2: <wall-clock, in flight, refusals, attempts> ; cap 4: <same> ; proposed cap <n>, because <one line>
B2: survives session <ok|ko> ; kill and resume <ok|ko> ; failed step skipped <ok|ko> ; space check <ok|ko> ; status command <the command>
PROPOSED NIGHT: <step: predicted duration> ; total <n> ; dropped <steps, or none>
PROPOSED SETTINGS: <list>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
WAITING FOR: GO
```
In the morning: the path of `reports/night-2/REPORT.md` and its section 1.
