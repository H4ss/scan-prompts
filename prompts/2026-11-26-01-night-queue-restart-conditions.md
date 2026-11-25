---
id: 2026-11-26-01
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: ready
supersedes: null
---

# Night queue: go for the restart, with three conditions

## Goal
Your plan is accepted: stop the queue (the scan in progress continues), clean the settings file of the main checkout, reorder, restart the queue from the corrected code, check the next scan. Three conditions apply.

## Inputs
`tools/night_queue.py`, `tools/night_queue.json`, the queue's state and log files, the run directory of the next scan.

## Steps

1. **Order.** Keep `a-m1-zones2`, in last position: `a-m1-baseline` (the scan in progress), `a-m1` (full settings), `b-m1`, `a-m2`, `b-m2`, `a-m1-repeat`, `a-m1-brief`, `b-m1-brief`, `a-m1-zones2`.

2. **Restart without a second scan.**
   - Before stopping the queue, show the code lines that handle a scan whose state is `running` when the queue resumes, so it is visible that the queue waits for it and does not submit it again.
   - In the state file, rename the entry of the scan in progress to `a-m1-baseline`. The new `a-m1` entry (full settings) must be `pending`. If the state still said `a-m1: running`, the full-settings scan would be taken for the one already started and would never run.
   - After the restart, print the state file. Expected: `a-m1-baseline` running, `a-m1` pending, nothing else started.

3. **Check on the right scan, at the right time.** The first scan after the baseline is `a-m1` with full settings. As soon as its zone generation is done, not at the end of the scan, verify: resolved settings show gap-fill on and batch size 25; `COVERAGE.json` holds gap-fill zones; triage runs in batches. Stay on watch until this check has passed. If it fails, hold the queue: no new scan starts, the running scan is not touched.

## Constraints
- One scan at a time. The scan in progress is never killed, restarted or re-run.
- No change to pipeline, skill or ranking code tonight.
- "It is active" always comes with the command output that shows it.

## Stop conditions
Stop and ask the maintainer when: the resume code would submit the running scan again and you cannot prevent it by editing the state file; the restart cannot be done without touching the scan in progress.

## Report
```
RESUME CODE: <file:lines, and what they do with a running scan>
STATE AFTER RESTART: <label: state, one per line>
MAIN CHECKOUT SETTINGS FILE: <restored, with the diff shown>
CHECK ON a-m1: <pending | passed, with the three proofs | failed, queue held>
```
