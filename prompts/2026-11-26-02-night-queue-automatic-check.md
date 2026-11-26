---
id: 2026-11-26-02
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: withdrawn
supersedes: null
---

# Night queue: make the check on the first full-settings scan automatic

## Goal
The restart is accepted. One gap remains: the check on `a-m1` is "pending" and depends on you, but you only act when a message arrives, and the maintainer is leaving. The check must run by itself, outside your session, and hold the queue if it fails.

## Inputs
`tools/night_queue.py` (read only), the queue's state and log files, the run directory of `a-m1` once it exists.

## Steps

1. Write `tools/night_check.py`, standard library only, started detached from your session (it must survive it), with its own log file. It does not import, restart or modify the running queue.
2. It waits, polling once a minute, until the scan labelled `a-m1` exists in the state file as running and its zone generation is finished.
3. Then it verifies, from the run's own outputs: the resolved settings show gap-fill on and batch size 25; `COVERAGE.json` holds at least one zone with origin `gapfill`, or the gap-fill log line says why none was created (no uncovered file with a signal is a valid reason; a setting that was not applied is not).
4. When triage of `a-m1` starts, it verifies that triage runs in batches (more than one batch session, or a single one only if the scan has 25 findings or fewer).
5. Result:
   - every check passes: it writes `CHECK PASSED` with the values read, and exits;
   - a check fails: it writes `CHECK FAILED` with the expected and the read values, then holds the queue so that no new scan starts. The running scan is not touched. It writes how to resume.
6. It gives up after 6 hours without `a-m1` reaching zone generation, writes `CHECK NOT RUN` with the reason, and holds nothing.
7. Test it before starting it: against the baseline scan's run directory it must report `CHECK FAILED` (that scan has no gap-fill and no batching), with the hold action disabled by a dry-run flag.
8. Also state what the queue does when `_wait_scheduler_free` reaches its 4-hour limit, and what state it gives a scan that ended in failure while the queue was waiting for it. If the answer is "it submits the next scan anyway" or "it marks it done", say so in the report; do not change the queue now.

## Constraints
- The running queue process and the running scan are not stopped, restarted or modified by this work. Only the failed-check path may hold the queue.
- No change to pipeline, skill or ranking code. New file: `tools/night_check.py` only.
- One commit, subject `night: automatic check on the first full-settings scan`.

## Stop conditions
Stop and ask the maintainer when: the checks cannot be read from the run's outputs without a model call; holding the queue would also stop the running scan.

## Report
```
CHECK SCRIPT: <path> ; pid <n> ; log <path>
DRY RUN ON BASELINE: <the CHECK FAILED lines it printed>
HOLD ACTION: <what it does exactly, and how to resume>
WAIT LIMIT: <what the queue does after 4 hours ; state given to a failed scan>
```
