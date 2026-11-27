---
id: 2026-11-26-07
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: superseded
supersedes: 2026-11-26-05
---

# Triage: no session whose context grows with the number of findings

Maintainer lines (filled when pasting):
```
DEV BRANCH: <branch to start from>
GATEWAY LIMIT: <maximum concurrent model requests the gateway accepts>
SMALLEST WINDOW: <context window, in tokens, of the smallest model used for scans>
REPLAY RUNS: <1 to 3 finished runs whose triage duration is known ; the smallest first>
```

## Goal
A triage batch of 25 findings still overflows the context window of the smaller model. Your own analysis gives the cause: the agent that coordinates a batch reads code in its own session, keeps every tool result and every sub-agent answer, and must still write the final file at the end. Batching divides the problem; it does not remove it, because the coordinator's context still grows with each finding.

The same cause explains the idle time you wanted to recover with parallel batches: a model session is doing the work of a loop.

Target design: **the loop is Python; a model session handles one finding and nothing else.** Then no context depends on the number of findings, batches disappear, and parallelism is a pool size. Finished scans, whose triage duration is known, are the test bench: triage is replayed on their stored findings, without scanning again.

This replaces the previous version of this prompt. If its tickets T1 to T3 are already done, keep them, add what is new in T1, and continue at T4. The setting `batch_parallelism` of the previous version is no longer wanted. Argue with evidence where you disagree.

## Inputs
Every finished run that still has its logs (triage logs, session logs, `run_metrics.json`, per-zone findings files, resolved settings), the triage skill and code, the settings file.

## Steps

### T1. Measure on finished runs (read-only, no model call)
Numbers come from the session logs. An estimate is marked `estimate` and never mixed with measures.

**a. Time.** One row per finished run in `docs/triage-facts.md`: triage settings (votes, batch size or single session, verifier agents per batch, model); wall-clock; findings in; batches; verifier calls started, failed, retried; sum of verifier durations; effective concurrency (that sum / wall-clock) and its share of `GATEWAY LIMIT`; time with no verifier running; gaps between batches; throttling errors.

**b. Context of the coordinating session.** For each batch session of each run: tokens at the end of each phase of the triage skill, split by source: skill text, findings file, code read by the coordinator itself, tool results, sub-agent answers, its own output. Then: tokens added per finding, and the largest number of findings that fits in `SMALLEST WINDOW` with 1 vote and with 3 votes. Say which batches overflowed, at which phase, and what happened to their findings.

**c. Phases.** One row per phase of the triage skill: what it does; does it need a model, or is it a rule; does it need to read the target's code; does it need to see several findings at once; what it adds to the coordinator's context.

**d. Votes and gap-fill.** Where 3 votes are stored: share of findings whose votes agree, share where the first vote equals the final verdict, both by severity. For runs with gap-fill: findings entering triage, kept, and kept by severity, split by zone origin (base, gap-fill).

A value the run did not store is `not recorded`, with the log line that would be needed.

### T2. Triage replay command
Runs the triage stage alone on what a finished run stored, into a new directory, without scanning: `--from-run <dir> --out <dir>`, plus overrides for the triage settings.
- Input: the findings exactly as they were before triage.
- Verifier agents read the target's code: the replay uses the same revision of the target as the source run, and the same inputs triage had then. If the source run did not record one of them, the command refuses and lists what is missing.
- The source run is never modified. Prove it with a checksum of its directory before and after.
- Output: the usual triage outputs, `run_metrics.json`, and `REPLAY.json` (source run, overrides, triage duration recorded by the source run).

### T3. Check the replay against the known duration
On the first of `REPLAY RUNS`, replay with exactly the triage settings of the original scan (`p0`). Compare with the original: wall-clock (expected within 20 %; outside that, find the reason first), findings per verdict and per severity, and the share of findings whose verdict or severity changed. That share is the **noise** of triage. If `p0` overflows like the original did, record it and go on: it is the reference.

### T4. Setting `stages.triage.driver: agent | python`
`agent` is today's behaviour, unchanged, and stays the default until T5 has decided. `python` works as follows.

1. **Grouping, in Python, before any model call.** Findings with the same file, the same category and overlapping lines form one group. Each group keeps the list of its members (`merged_from`). When in doubt, do not merge: a wrong merge hides a finding, a missed one costs one extra verification. Count the groups in the metrics.
2. **Verification: one session per group and per vote.** The session receives one group and a verifier skill that holds the verifier instructions only, taken from the current triage skill with as few word changes as possible. It writes one small result file with a fixed schema (`triage/votes/<id>.<n>.json`). Python validates the file; missing or invalid means one retry, then the vote is `error`.
3. **Vote count in Python**, with the rule the skill applies today (quote it in the report). A group without enough valid votes is `untriaged`: reported as today, never dropped, never counted as rejected.
4. **Ranking: one session per kept group**, facts only, then `ranking.py` derives the severity as it does now. The challenge step is unchanged.
5. **Assembly of the final triage file in Python.**
6. **One pool** for all these sessions, size `stages.triage.max_sessions`, refused at load time above `GATEWAY LIMIT`. No batch.
7. **Resumable.** Results are files. A second start skips what already has its result, so a crash of the driver or of one session loses nothing else.
8. **Metrics** per session: duration, tokens in, out, cached, peak context. Per run: the largest peak context of any session.

If T1c shows a phase that really needs judgement across several findings (for example two findings that only matter together), it becomes one extra session that receives one line per group (id, file, category, title) and no code. Its context grows by one line per group, not by the code of each.

Unit tests with a fake session: grouping (overlap, no overlap, same lines in two files), vote rule, `error` and `untriaged`, resume after an interrupted run, refused pool size.

### T5. Replays
Only when the scheduler is free. Same model and same votes as the original scan of each run.

| replay | driver | compared with | answers |
|---|---|---|---|
| `p0` | agent, original settings | the original, recorded | noise ; is the replay faithful (first run only, this is T3) |
| `py` | python | the original, and `p0` where it exists | context, time, tokens, verdicts |

For each `py`: largest peak context of any session; wall-clock; effective concurrency; tokens in, out and cached, against the original; `untriaged` and `error` counts; share of verdicts and severities changed against the original; groups merged by Python against findings merged by the agent in the original (how many differ, three examples described without code).

Verdict, `python` becomes the default if on every replayed run:
- no session goes above half of `SMALLEST WINDOW`, and the largest peak is about the same on the smallest and the largest run;
- no finding is lost: every input finding is in a group, every group has a verdict or is `untriaged`;
- the share of changed verdicts is no more than the noise of T3 plus 2 points, or each larger difference is explained;
- wall-clock is not worse than the original. Total tokens may be higher; report by how much.

Otherwise the default stays `agent` and the report says which condition failed.

If time is short, T1, T2 and T3 come first and can be reported alone.

## Constraints
- New branch `feat/triage-replay` in its own worktree, from `DEV BRANCH` (same branch as the previous version of this prompt). A running scan, its worktree and its process are not touched.
- No change to the wording of the verifier and ranker instructions beyond what the split requires; list every sentence changed. No change to the vote count or the ranking code.
- With `driver: agent` the triage is the same as before this work.
- One commit per ticket, subject `triage: <ticket> <what>`.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: no finished run stored its findings as they were before triage; the target's revision of a source run cannot be found; a phase of the skill needs the code of several findings in one session and you see no way around it; the pipeline cannot start a model session per finding from Python the way the scan stage starts one per zone.

## Report
```
T1 TIME: runs <n> ; share of gateway limit used <x % per run> ; time with no verifier <x %> ; throttling <n>
T1 CONTEXT: per finding <n tokens, measured|estimate> ; biggest source <name, x %> ; fits <n findings at 1 vote, n at 3 votes> ; overflowed batches <n>, their findings <state>
T1 PHASES: <phase: model yes/no, code yes/no, several findings yes/no>
VOTES: unanimous <x %> ; first vote = final verdict <x %> ; or not recorded
GAP-FILL: base zones <in / kept> ; gap-fill zones <in / kept>
T2: <command> ; source run unchanged <proof>
T3: original <time> ; p0 <time> ; noise: verdict changed <x %>, severity changed <x %>
T4: tests <passed/total> ; sentences changed in the instructions <n>
T5: per run: peak context <n> ; time <original / py> ; tokens <original / py> ; verdicts changed <x %> ; untriaged <n> ; grouping differences <n> ; verdict <python default | agent stays, condition failed>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
