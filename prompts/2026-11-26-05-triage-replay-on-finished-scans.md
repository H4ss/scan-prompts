---
id: 2026-11-26-05
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: superseded
supersedes: 2026-11-26-04
---

# Triage: replay it on scans that already exist, with their known duration as the reference

Maintainer lines (filled when pasting):
```
DEV BRANCH: <branch to start from>
GATEWAY LIMIT: <maximum concurrent model requests the gateway accepts>
REPLAY RUNS: <1 to 3 finished runs whose triage duration is known ; the smallest first>
```

## Goal
Triage is the longest stage, and gap-fill about doubles the number of findings that reach it. Finished scans exist, and their triage duration is known. Use them instead of scanning again:

1. measure, from what those scans stored, where the triage time went;
2. replay the triage stage alone on their stored findings, changing one setting at a time. The recorded triage of the original scan is the reference, at no cost.

You proposed to run triage batches in parallel, with an estimated gain of 2 to 3 times. One batch already uses as many verifier agents as the gateway accepts, so parallel batches at the same total number of agents only gain the time during which a batch keeps agents idle. The measure says how much that is. Argue with evidence where you disagree.

## Inputs
Every finished run that still has its logs (triage logs, session logs, `run_metrics.json`, per-zone findings files, resolved settings), the triage code, the settings file, your parallel-triage ticket.

## Steps

### T1. Measure on finished runs (read-only, no model call)
One row per finished run in `docs/triage-time-facts.md`, not only the `REPLAY RUNS`:

| value | definition |
|---|---|
| triage settings | votes, batch size or single session, verifier agents per batch, model |
| wall-clock | triage start to triage end |
| findings in, batches | counts |
| verifier calls | number started, failed, retried |
| verifier time | sum of the durations of all verifier calls |
| effective concurrency | verifier time / wall-clock |
| utilisation | effective concurrency / `GATEWAY LIMIT` |
| orchestrator time | time with no verifier running: before the first one starts, between waves, after the last one ends |
| gap between batches | end of batch n to start of batch n+1 |
| throttling | rate-limit or timeout errors from the gateway |
| vote agreement | where 3 votes are stored: share of findings whose votes agree ; share where the first vote equals the final verdict ; both by severity |

For each run that used gap-fill, a second table: findings that entered triage, kept, rejected, and kept by severity, split by zone origin (base zones, gap-fill zones). It says whether the doubled input is doubled value or doubled work.

A value that the run did not store is written `not recorded`, with the log line that would be needed. No estimate.

**Decision, written under the tables:**
- utilisation at 70 % or more: the gateway is already the limit, parallel batches cannot give 2 times. Skip T4 and the `p3` replays; say what the measure points to instead (number of verifier calls, verifier duration, orchestrator time).
- utilisation under 70 %: do T4 and `p3`. The gain is at most `1 / utilisation`; write that number.

T2 and T3 are done in both cases.

### T2. Triage replay command
Runs the triage stage alone on what a finished run stored, into a new directory, without scanning: `--from-run <dir> --out <dir>`, plus overrides for the triage settings.
- Input: the findings exactly as they were before triage.
- Verifier agents read the target's code: the replay uses the same revision of the target as the source run, and the same inputs triage had then. If the source run did not record one of them, the command refuses and lists what is missing.
- The source run is never modified. Prove it with a checksum of its directory before and after.
- Output: the usual triage outputs, `run_metrics.json`, and `REPLAY.json` (source run, overrides, triage duration recorded by the source run).

### T3. Check the replay against the known duration
On the first of `REPLAY RUNS`, replay with exactly the triage settings of the original scan (`p0`). Compare with the original:
- wall-clock: expected within 20 %. Outside that, find the reason before going on (gateway load, a setting that differs, a cache) and write it.
- findings per verdict and per severity, and the number of findings whose verdict or severity changed. This rate is the **noise** of triage: two identical triages of the same findings. No other replay can be judged without it.

### T4. Setting `stages.triage.batch_parallelism` (only if T1 says so)
- Default 1: exactly today's behaviour, same code path as far as possible.
- Above 1, the number of verifier agents per batch is derived so that `batch_parallelism × agents per batch` never exceeds `GATEWAY LIMIT` (itself a setting). A configuration that would exceed it is refused at load time.
- A batch that fails is retried once. If it fails again, its findings get the state `untriaged`: never dropped, never counted as rejected, and the run's summary says how many.
- Batch results are merged in batch order; the output does not depend on which batch finished first.
- An exception in a worker is logged with its batch number and fails that batch; the pool never swallows it.
- `run_metrics.json` gets, per batch: start, end, verifier calls, failures, retries, throttling errors.
- Unit tests with a fake verifier: order independence, failed batch gives `untriaged`, refused configuration.

### T5. Replays, one setting changed at a time
Only when the scheduler is free: a replay during a scan measures nothing and slows the scan. Same model and same votes as the original scan of each run.

| replay | triage settings | compared with | answers |
|---|---|---|---|
| `p0` | those of the original | the original, recorded | noise ; is the replay faithful (first run only, this is T3) |
| `p1` | batches of 25, one at a time | the original | what batching alone changes. Skip if the original already ran this way |
| `p3` | batches of 25, three at a time | `p1`, or the original if `p1` was skipped | gain of parallel batches |

For each replay: wall-clock, effective concurrency, throttling errors, retries, tokens in and out, `untriaged` count, and against its reference the share of findings whose verdict changed and whose severity changed.

Verdict: parallel batches are accepted if, on every replayed run, `p3` is at least 1.5 times faster than its reference, has no `untriaged` finding, and its share of changed verdicts is no more than the noise of T3 plus 2 points. Otherwise the default stays 1 and the report says why.

If time is short, T1, T2 and T3 come first and can be reported alone.

## Constraints
- New branch `feat/triage-replay` in its own worktree, from `DEV BRANCH`. A running scan, its worktree and its process are not touched.
- No change to the verifier prompt, the vote count, the batch size default or the ranking code. Vote agreement is a measure only.
- The default settings after this work give the same triage as before.
- One commit per ticket, subject `triage: <ticket> <what>`.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: no finished run stored its findings as they were before triage; the target's revision of a source run cannot be found; the gateway returns throttling errors with one batch at a time already.

## Report
```
T1: runs measured <n> ; utilisation <x % per run> ; orchestrator time <x %> of triage ; gaps <x %> ; throttling <n> ; decision <no parallel batches | continue, gain at most x>
GAP-FILL: base zones <in / kept> ; gap-fill zones <in / kept> ; kept by severity <...>
VOTES: unanimous <x %> ; first vote = final verdict <x %> ; or not recorded
T2: <command> ; source run unchanged <proof>
T3: original <time> ; p0 <time> ; noise: verdict changed <x %>, severity changed <x %>
T4: tests <passed/total> ; default path unchanged <proof> ; or skipped
T5: per run: p1 <time, changed x %> ; p3 <time, changed x %, untriaged n> ; gain <x> ; verdict <accepted | default stays 1>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
