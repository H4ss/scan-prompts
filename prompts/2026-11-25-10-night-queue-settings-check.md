---
id: 2026-11-25-10
date: 2026-11-25
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: ready
supersedes: null
---

# Night queue: prove the settings are applied, and argue the points you disagree with

## Goal
The queue is running its first scan. A reviewer who read your last messages thinks the scans after it will run exactly like the first one, without gap-fill and without triage batches. Before the maintainer leaves for the night, either prove the reviewer wrong with command output, or fix it. For every point below, say whether you agree; where a point is debatable, argue your case with evidence instead of complying silently.

## Inputs
The night worktree, `tools/night_queue.py`, `tools/night_queue.json`, the queue's state and log files, the settings file the pipeline actually reads, the run directory of the scan in progress, the settings file of the main checkout.

## Steps

### 1. Check the reviewer's claims (read-only, do this first)
Answer each claim with `TRUE` or `FALSE` and the command output that shows it.

- C1. The queue process that is running was started before `night_queue.py` was edited. A running Python process keeps the old path in memory, so it will still write the settings file of the main checkout for the next scans.
- C2. Your direct write to the settings file of the night worktree failed (`No module named 'yaml'`). The check you ran right after printed gap-fill `off` and batch size `None`. "validation OK" only says the file loads.
- C3. So, as things stand, the next scan would start with gap-fill off and no batching.
- C4. The queue wrote in the settings file of the main checkout, which was meant to stay untouched.
- C5. The threat model reaches zone generation but not the ranking prompt, in the scan in progress and in every earlier run. Therefore the earlier comparison "ranking with threat model on / off" measured nothing on that point.
- C6. Triage votes were changed from 1 to 3 today. Batching reduces the context of a triage session; it does not reduce the number of verifier agents, so the estimate "20 to 40 minutes of triage with batches" has no measurement behind it.

### 2. Give your position on the reviewer's proposals
For each proposal: `AGREE`, or `DISAGREE` with your reason, your evidence and what you would do instead. Disagreeing is welcome when you know something the reviewer cannot see from outside.

- P1. Make the next scans really receive their settings. No second scan in parallel, the scan in progress is not killed and not re-run. If the queue must be restarted, say exactly how the state file prevents a re-run.
- P2. When the next scan has finished zone generation, check its run: resolved settings show gap-fill on and batch size 25, `COVERAGE.json` holds gap-fill zones, triage runs in batches. If one is missing, stop the queue, fix, restart from that scan. Stay on watch until this check has passed.
- P3. Restore the settings file of the main checkout to what it was before the queue wrote in it. Show the diff first.
- P4. New order: `a-m1` with full settings first, then `b-m1`, `a-m2`, `b-m2`, `a-m1-repeat`, `a-m1-brief`, `b-m1-brief`. Drop `a-m1-zones2`. The scan in progress is relabelled `a-m1-baseline` (no gap-fill, no batching). Reason: the full-settings scan of target A with model 1 is the most useful one and must not sit in fifth position.
- P5. Votes stay at 3 for every scan of the night, since the scan in progress already uses 3.
- P6. The threat-model-to-ranking bug is not fixed tonight: changing pipeline code while a scan runs from the same directory, with nobody watching, costs more than it brings. Write it as a ticket, and state in `REPORT.md` that in every scan of this night the threat model reached the zones but not the ranking.

### 3. Act
- P1, P2 and P3 follow from facts. If C1 to C4 are `TRUE`, do them now without waiting. If your evidence shows a claim is `FALSE`, show it and skip the matching action.
- P4, P5 and P6 are choices. Apply the reviewer's version unless you disagreed in step 2; where you disagreed, wait for the maintainer's answer.
- If the scan in progress ends before the maintainer has answered and the next scan would start with wrong settings, hold the queue (no new scan starts) rather than let it run. Holding must not touch a running scan.

## Constraints
- One scan at a time. The scan in progress is never killed, restarted or re-run.
- No change to pipeline, skill or ranking code tonight. Only the queue script, the queue table, the settings files and the report may change.
- Every statement of the form "it is fixed" or "it is active" comes with the command output that shows it.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: making the next scans receive their settings would require killing or re-running the scan in progress; you cannot tell which settings file the pipeline reads; the main checkout's settings file had local changes you cannot tell apart from the queue's.

## Report
```
CLAIMS: C1 <TRUE|FALSE> ; C2 ... ; C6 ...   (evidence under each)
POSITIONS: P1 <AGREE|DISAGREE> ; P2 ... ; P6 ...   (reason and alternative under each DISAGREE)
DONE NOW: <what you changed, with the proof it is active>
WAITING FOR THE MAINTAINER: <points, or none>
QUEUE: <order and state of every scan> ; next check: <what you will verify on the next scan, and when>
```
