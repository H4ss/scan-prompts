---
id: 2026-11-26-04
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: superseded
supersedes: null
---

# Triage: measure where the time goes, then run batches in parallel if the measure says so

Maintainer lines (filled when pasting):
```
DEV BRANCH: <branch to start from>
GATEWAY LIMIT: <maximum concurrent model requests the gateway accepts>
REPLAY RUN: <finished run whose findings are used for the replays>
```

## Goal
Triage is now the longest stage. You proposed to run triage batches in parallel, with an estimated gain of 2 to 3 times. The idea is sound, but the gain is an estimate, and one batch already uses as many verifier agents as the gateway accepts. Parallel batches at the same total number of agents only gain the time during which a batch keeps agents idle. So: measure that idle time first, on runs that already exist. Build only if the measure leaves room. Argue with evidence where you disagree.

## Inputs
The finished runs of the night (triage logs, session logs, `run_metrics.json`), the triage batching code, the settings file, your parallel-triage ticket.

## Steps

### T1. Measure on finished runs (read-only, no model call)
For the triage stage of each finished run, write one row in `docs/triage-time-facts.md`:

| value | definition |
|---|---|
| wall-clock | first batch start to last batch end |
| batches, findings, votes | counts |
| verifier calls | number started, number failed, number retried |
| verifier time | sum of the durations of all verifier calls |
| effective concurrency | verifier time / wall-clock |
| utilisation | effective concurrency / `GATEWAY LIMIT` |
| orchestrator time | per batch, time with no verifier running: before the first one starts, between waves, after the last one ends |
| gap between batches | end of batch n to start of batch n+1 |
| throttling | number of rate-limit or timeout errors from the gateway |
| vote agreement | share of findings whose 3 votes agree ; share where the first vote equals the final verdict ; both split by severity |

If a value cannot be read from what the run stored, write `not recorded` and say which log line would be needed. Do not estimate.

**Decision, written under the table:**
- utilisation at 70 % or more: the gateway is already the limit. Parallel batches cannot give 2 times. Stop after T1 and report; say what the measure points to instead (number of verifier calls, verifier duration, orchestrator time).
- utilisation under 70 %: continue with T2 to T4. The expected gain is at most `1 / utilisation`; write that number.

### T2. Triage replay
A command that runs the triage stage alone on the findings stored by a finished run, into a new output directory, without scanning again: `--from-run <dir> --out <dir> [--sample <n>] [--seed <n>]`. The source run is never modified. `--sample` takes a fixed, seeded subset so that two replays triage exactly the same findings. This command is also what later tests of the triage stage will use.

### T3. Setting `stages.triage.batch_parallelism`
- Default 1: exactly today's behaviour, same code path as far as possible.
- When above 1, the number of verifier agents per batch is derived so that `batch_parallelism × agents per batch` never exceeds `GATEWAY LIMIT` (itself a setting). A configuration that would exceed it is refused at load time.
- A batch that fails is retried once. If it fails again, its findings are written with the state `untriaged`: never dropped, never counted as rejected, and the run's summary says how many.
- Batch results are merged in batch order. The output must not depend on which batch finished first.
- An exception in a worker is logged with its batch number and fails that batch; it is never swallowed by the pool.
- `run_metrics.json` gets, per batch: start, end, verifier calls, failures, retries, throttling errors.
- Unit tests with a fake verifier: order independence, failed batch gives `untriaged`, refused configuration.

### T4. Measure by replay
Only when the scheduler is free: a replay during a scan measures nothing and slows the scan.
Same 75 findings (`--sample 75 --seed 1`) from `REPLAY RUN`, same model, same votes:

| replay | batch_parallelism | purpose |
|---|---|---|
| r1 | 1 | reference |
| r2 | 1 | how much two identical triages differ (noise) |
| r3 | 3 | the gain, and whether verdicts move more than the noise |

For each: wall-clock, effective concurrency, throttling errors, retries, tokens in and out. Between r1 and r2, and between r1 and r3: number of findings whose verdict changed, number whose severity changed.
Verdict rule: parallel batches are accepted if r3 is at least 1.5 times faster than the mean of r1 and r2, has no `untriaged` finding, and differs from r1 no more than r2 does (plus two findings of tolerance). Otherwise the default stays 1 and the report says why.

## Constraints
- New branch `feat/triage-parallel` in its own worktree, from `DEV BRANCH`. If a queue is running, its worktree, its process and its scans are not touched, and T4 waits.
- No change to the verifier prompt, the vote count, the batch size or the ranking code. Vote agreement in T1 is a measure only; do not change voting.
- The default settings after this work give the same triage as before.
- One commit per ticket, subject `triage: <ticket> <what>`.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: T1 says utilisation is 70 % or more (report, do not build); the stored findings of a finished run are not enough to replay triage; the gateway returns throttling errors at `batch_parallelism` 1 already.

## Report
```
T1: utilisation <x %> on <n> runs ; orchestrator time <x %> of triage ; gaps <x %> ; throttling <n> ; decision <stop | continue, gain at most x>
VOTES: unanimous <x %> ; first vote = final verdict <x %> ; by severity <...>
T2: <command> ; source run unchanged <proof>
T3: tests <passed/total> ; default path unchanged <proof>
T4: r1 <time> ; r2 <time> ; r3 <time> ; gain <x> ; verdict changes r1-r2 <n> ; r1-r3 <n> ; untriaged <n> ; verdict <accepted | default stays 1>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
