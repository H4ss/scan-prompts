---
id: 2026-11-27-01
date: 2026-11-27
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: ready
supersedes: 2026-11-26-07
---

# Triage: back to one session with 16 sub-agents, nothing lost when it stops, time per phase, one measure

Maintainer lines (filled when pasting):
```
SOURCE RUN: <full scan of last night ; its findings before triage are the input of the measure>
REFERENCE RUN: <finished run whose triage ran as one session with 16 sub-agents>
PARALLEL REPLAY: <last night's replay of the triage of SOURCE RUN, 3 batches at once>
```

## Goal
Last night settled the question of batches. On the same findings, triage in batches, one at a time or three at once, was slower per finding than the single session of `REFERENCE RUN`, left findings `untriaged` when a batch died, and found fewer duplicates because a batch only sees its own part. The single session was still the best of the three, although its wall limit stopped it twice.

So triage goes back to one session. Three defects are fixed on the way, the same ones the scan stage had:

1. the session is stopped by a wall limit that does not look at whether work is going on;
2. the step limit is fatal and is never retried;
3. verdicts are written at the end, so a session that stops loses everything it had judged.

Then **one** measure, and only one: a replay of the triage of `SOURCE RUN`. It must leave a picture of where the triage time goes, phase by phase, so that what is left to improve is known without another run.

Decisions already taken by the maintainer:
- one triage session, no batch, no parallel batches;
- 16 sub-agents, as in `REFERENCE RUN`;
- one measure. No scan, no second replay.

Argue with evidence where you disagree on anything else.

## Inputs
Branch `feat/night-2` (tag `night-2`), the triage skill and code, the unit runner and its retry policy, the replay command and the launcher of last night, the settings file, the logs and outputs of the three runs named above, `reports/night-2/REPORT.md`.

## Steps

## Part 1 — facts from existing logs (read-only, no model call)

Write them in `docs/triage-single-session-facts.md`. A value that the logs do not hold is `not recorded`; an inferred one is marked `estimate`.

### F1. What the stops of the reference run cost
For each attempt of the triage session of `REFERENCE RUN`: duration, how it ended, what the next attempt started from (same session resumed with its context, or from nothing), and which findings were verified again. Then one number: the share of the triage time spent on work done again. This says how long that triage would have lasted without its stops.

### F2. Steps, context, gateway
- Steps used by the coordinator, per attempt and in total.
- Context of the coordinator at the end of each attempt, against the window of the model.
- Refusals by the gateway during the triage of `REFERENCE RUN`, with 16 sub-agents. A non-zero count is reported; it does not change the decision.

### F3. The phases of the triage skill
One row per phase, in order: what it does; who does the work (coordinator, sub-agents, Python); what it writes and where; what later phases need from it.

## Part 2 — build

New branch `feat/triage-single-session` from `feat/night-2`, in its own worktree. One commit per ticket, subject `triage: <ticket> <what>`.

### N1. Settings
- One triage session: no batch size, `batch_parallelism` at its default. The batch code stays as it is, behind its settings; it is not removed here.
- `stages.triage.max_subagents: 16`.
- Votes, challenge and model as in `SOURCE RUN`.

### N2. The session is watched like a scan unit
- The triage session is alive while anything in its session tree is active (coordinator, any sub-agent, a model request in flight). It is idle only when nothing happened in the tree for the idle timeout. If triage does not go through the unit runner, say what watches it today and apply the same rule there.
- The wall limit of the triage unit is no longer the watch. It becomes a safety net, set for the measure to twice the predicted duration (Part 3).

### N3. Nothing is lost when the session stops
Today a session that stops before its last phase leaves no verdict. Change that with the smallest wording possible in the triage skill, and quote every sentence changed.

- **Each phase leaves its output in a file** when it ends (for example the groups of duplicates). A later attempt reads it and does not do that phase again.
- **One file per verdict**, written once, as soon as the verdict of a finding is settled, and never touched again: `<out-dir>/triage/verdicts/<finding-id>.json`, with everything the final triage file needs for that finding (verdict, duplicate of which finding, the facts used for ranking). Choose who writes it and justify: the sub-agent itself, which then answers the coordinator in one line, or the coordinator after each answer. The first keeps the coordinator's context small; take it if the sandbox lets a sub-agent write there.
- **Python assembles the final triage file** from the verdict files, at the end and after any interruption. The coordinator no longer types it. A finding is `untriaged` only when it has no verdict file, and its line says why (which attempt stopped, for which cause).
- **A new attempt starts from what is on disk**: the first phase without output, and inside verification the first finding without verdict. It receives the skill, the findings, the phase outputs and the list of findings already judged. It does not receive the old conversation.

### N4. The step limit and the retry table
- Set `stages.triage.max_turns` to twice the total of steps measured in F2.
- Add the triage session to the retry table of the scan units, with one row more:

| cause | action | counts as an attempt |
|---|---|---|
| step limit reached | new session from what is on disk (N3) | yes |
| context full | new session from what is on disk | yes |
| idle | resume once, with a short message saying what was pending | yes |
| idle again at the same last event | new session from what is on disk | yes |
| refused by the gateway, request stalled | the request is sent again | no |

With N3, a context that fills up is no longer a failure of the triage: the session is replaced and the work goes on with what is left.

### N5. Time per phase, in the metrics
`run_metrics.json` gets one entry per phase of the triage skill:

| value | definition |
|---|---|
| start, end, duration | per attempt, then summed |
| coordinator alone | time with no sub-agent running |
| sub-agent calls | started, failed, started again |
| sub-agent time | sum of their durations ; with the duration of the phase it gives the number working at once |
| tokens in, out | of the coordinator, and of its sub-agents |
| steps | used by the coordinator |
| context | of the coordinator at the end of the phase |
| requests in flight | highest, and refusals |

Phase limits are derived by Python from the session's own events (the write of each phase's output file, the start of sub-agents), not from what the model says about itself.

### N6. Tests, without a model
With a fake session: a session stopped during verification leaves verdict files that are byte-identical after the next attempt; the next attempt does not judge them again; a finding without verdict file is `untriaged` with its cause; the step limit starts a new session and loses nothing; the assembled file does not depend on the order in which verdicts were written; the phase times add up to the duration of the session.

## Part 3 — the one measure (scheduler free)

### M1. Prediction, written before the start
From F1: time per finding of `REFERENCE RUN` without the work done again, applied to the number of findings of `SOURCE RUN`. Write the predicted duration, and the predicted share of each phase.

### M2. The replay
Triage alone on the findings of `SOURCE RUN` as they were before triage, with the replay command, into a new directory, with the settings of N1 to N5. `SOURCE RUN` is not modified (checksum before and after).

- Started through last night's launcher, detached from your session, with its restart wrapper and its status command.
- Before the start, the launcher compares the resolved settings with N1 to N4: one session, 16 sub-agents, tree liveness, step limit, safety net. A difference means no start.
- Stay on watch until you have shown: the first phases done with their output files, the first verdict files, the number of sub-agents alive, requests in flight being recorded.
- Time limit: twice the prediction. Past it the replay is stopped and the report is built from what is on disk.
- A restart that continues the same replay directory is the same measure. A new replay from the start is not allowed without the maintainer.

When the maintainer writes `status`: run the status command and show its screen. If the launcher and its wrapper are gone, start them again through the resume path. Never edit code or settings during the measure.

### M3. Report `reports/triage-single-session/REPORT.md`, generated by a script from the run outputs
1. **Four triages side by side**: `REFERENCE RUN`, the triage of `SOURCE RUN` (batches, one at a time), `PARALLEL REPLAY`, this replay. Rows: findings in; wall-clock; findings judged per minute; `untriaged`; share of duplicates found; attempts and their causes; share of time spent on work done again; tokens in and out; highest requests in flight; refusals.
2. **Where the time goes**: the table of N5 for this replay, one row per phase, with the share of each phase in the total, next to the prediction of M1. Add the same rows for `REFERENCE RUN` where its logs let the phases be recognised, marked `estimate`.
3. **Three triages of the same findings** (the triage of `SOURCE RUN`, `PARALLEL REPLAY`, this replay), counted in Python:
   - findings judged by all three: share with the same verdict in all three; then each pair;
   - findings confirmed by all three: share with the same severity; for the others, the ranking facts that differ between runs, counted per fact;
   - `untriaged` in one run and judged in another: counted apart, never as a disagreement.
   The list of findings whose severity differs is written to a local file; it is the input of the work on classification.
4. **Context**: highest context of the coordinator, context added per finding, and the number of findings one session holds before it is replaced (`estimate`).
5. **What is left to improve**, three lines at most, from the table of point 2: the phase, its share of the time, whether sub-agents or the coordinator hold it, what would reduce it, and the gain to expect. Facts and estimates only; nothing is built.

### Verdict
The single session is the recommended triage setting if, on this replay:
- no finding is `untriaged` because a session stopped;
- its wall-clock is under that of both batched triages of the same findings, and its findings judged per minute are not under those of `REFERENCE RUN`;
- work done again is under 5 % of the triage time.

Otherwise say which condition failed, with the numbers.

## Constraints
- One measure: the replay of M2. No scan, no other replay, no artificial load on the gateway.
- No change to the wording of the verifier and ranker instructions beyond where they write their result; no change to the vote count, the challenge or the ranking code. List every sentence changed in the triage skill.
- The scan stage is not touched. A running scan that is not part of this work, its worktree and its process are not touched.
- The batch settings keep their defaults and their behaviour.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: one file per verdict needs more than a few sentences changed in the triage skill; `SOURCE RUN` did not store its findings as they were before triage; the replay command cannot run triage as one session; the facts of F1 show that the stops of `REFERENCE RUN` were not the reason of its duration, so that the prediction is above the duration of the batched triages.

## Report
Before the measure:
```
F1: attempts <n> ; each next attempt started from <resumed session | nothing> ; work done again <x % of triage time>
F2: steps <n> ; coordinator context <n> of a window of <n> ; refusals with 16 sub-agents <n>
F3: <phase: who, writes what>
N1: resolved triage settings <list>
N2: watched by <tree liveness | other, what> ; safety net <value>
N3: verdict file written by <sub-agent | coordinator>, because <one line> ; sentences changed <quotes>
N4: step limit <old> -> <new> ; rows added to the retry table <n>
N5: phase limits derived from <which events>
N6: tests <passed/total>
PREDICTION: <duration>, phases <shares>
```
After the measure:
```
MEASURE: wall-clock <n> against prediction <n> ; findings in <n>, judged <n>, untriaged <n, causes> ; duplicates <x %> ; attempts <n, causes> ; work done again <x %> ; highest in flight <n> ; refusals <n>
PHASES: <phase: duration, share, coordinator alone, sub-agents at once>
SAME FINDINGS, THREE TRIAGES: same verdict in all three <x %> ; same severity among confirmed <x %> ; facts that differ most <list>
CONTEXT: highest <n> ; per finding <n> ; findings held by one session <n, estimate>
LEFT TO IMPROVE: <three lines at most>
VERDICT: single session <recommended | not, condition failed>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
