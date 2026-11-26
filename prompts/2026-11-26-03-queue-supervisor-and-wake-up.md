---
id: 2026-11-26-03
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: superseded
supersedes: null
---

# Unattended queue: supervisor without a model, model woken only on an event

Maintainer lines (filled when pasting):
```
DEV BRANCH: <branch to start from>
WAKE MODEL: <model used by the watch sessions>
MAX WAKES: 6
```

## Goal
Last night the queue script crashed and nobody restarted it, because you only act when a message arrives. A scan queue must finish without a person and without your session. Two layers:

1. a supervisor in plain Python that restarts the queue and records what happens, with no model call;
2. a watch session of opencode, started by the supervisor only when something happened that a script cannot judge.

A model that wakes up every few minutes to read "all is fine" costs tokens and adds nothing. The model is woken on an event, not on a timer.

## Inputs
`tools/night_queue.py`, its queue table, state file and log; the scheduler's `queue` command; `opencode run --help` and `opencode --help` on this machine (read them, do not assume flag names).

## Steps

### T1. What happened last night (read-only, first)
From the logs: which process stopped, at what time, the traceback or the signal, how long the queue stayed down, which scans were lost or delayed, and what state the state file was left in. Write it at the top of the report. Fix the cause only if the fix is in the queue script.

### T2. Supervisor `tools/queue_supervisor.py` (standard library only)
- Starts the queue as a child process and stays alive itself, detached from any terminal and from your session. Show the command that proves it survives the session (process parent, session id).
- If the queue process exits while scans are still pending: restart it through the existing resume path (it waits for a running scan and never submits it again). At most 3 restarts per hour; after that, stop restarting and raise the event `crash_loop`.
- Every minute, writes `queue_heartbeat.json`: time, supervisor pid, queue pid, scan in progress, its stage, time of the last line written in the scan's log, number of restarts.
- Appends one line per event to `QUEUE_JOURNAL.md` (time, event, what was done). This file is what the maintainer reads first in the morning.
- Deterministic checks belong here, not in a model: after zone generation of each scan, compare the scan's resolved settings with its row in the queue table; a difference raises the event `settings_mismatch` and holds the queue.
- Commands: `start`, `status`, `hold` (no new scan starts, the running scan is not touched), `resume`, `stop` (stops the supervisor and the queue, never a scan).

### T3. Events
The supervisor raises an event, written to the journal, in these cases only:

| event | condition |
|---|---|
| `crash_loop` | restart limit reached |
| `scan_failed` | a scan ended in failure |
| `scan_stuck` | no new line in the scan's log for 30 minutes while the scheduler says it runs |
| `settings_mismatch` | resolved settings differ from the queue table |
| `wait_limit` | the queue reached its maximum wait for the scheduler |

Thresholds are constants at the top of the file.

### T4. Watch session, woken by an event
- On an event, the supervisor starts one fresh non-interactive opencode session (never a continuation of an existing session: its context would grow all night), with `WAKE MODEL`, and waits for it with a 15-minute timeout. No more than `MAX WAKES` sessions per queue; after that, events are only journaled and the queue is held.
- Find in `opencode run --help` how to start a non-interactive session with a given agent and model. If the installed version cannot do it, stop and report; do not build a workaround that types into a terminal.
- The session runs as an agent `queue-watch` with a skill `.opencode/skills/queue-watch/SKILL.md`. The skill says: read the heartbeat, the journal's last 30 lines, the state file and the last 100 lines of the failing log; state the cause in two lines; choose one action from the closed list; write the decision to the journal.
- Closed list of actions, each one a subcommand of `tools/queue_watch.py`: `note <text>`, `hold`, `resume`, `skip <label>` (marks one pending or failed scan as skipped, with the reason), `restart-queue`.
- Enforce the list with the agent's permissions, not with prose: edit denied everywhere; shell allowed for `python tools/queue_watch.py *` and for read commands on the queue files and run directories; everything else denied. Nothing may be left on "ask": with nobody there, a question blocks the session. Prove it: run the agent once with an instruction to edit a file and show the refusal, and show that the session ended instead of waiting.
- The watch session never: edits code or settings, kills or re-submits a scan, commits, starts a scan outside the queue.

### T5. Tests, without a real scan
- A queue table whose "scans" are a short sleep command (add a dry-run mode to the queue if it has none; it must not call the scheduler).
- Kill the queue process: the supervisor restarts it, the journal shows it, no scan runs twice.
- Kill it four times in a row: `crash_loop`, restarts stop, one watch session starts.
- Simulate `scan_stuck` and `settings_mismatch` on copies of the state files: the right event is raised, the queue is held.
- Close your own terminal session between two steps: the supervisor is still there.

### T6. README section
Half a page in the tools README: start a queue under the supervisor, read the journal, hold and resume, what each event means.

## Constraints
- If a queue is running now: work in another worktree on a new branch `feat/queue-supervisor` from `DEV BRANCH`, and do not stop, restart or modify the running queue or its scans. Putting the running queue under the supervisor needs the maintainer's go.
- No change to pipeline, skill or ranking code. New files under `tools/` and `.opencode/` only, plus the dry-run mode of the queue.
- One commit per ticket, subject `queue: <ticket> <what>`.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: opencode on this machine has no non-interactive mode; permissions cannot deny edits for one agent while your own session keeps them; a test would need a real scan.

## Report
```
LAST NIGHT: <process> stopped at <time> ; cause <traceback line or signal> ; down for <duration> ; scans lost <labels>
SUPERVISOR: <path> ; survives the session: <proof>
EVENTS TESTED: crash restart <ok|ko> ; crash_loop <ok|ko> ; scan_stuck <ok|ko> ; settings_mismatch <ok|ko>
WATCH SESSION: command used <exact command> ; edit refused <proof> ; ended without waiting <proof>
NOT DONE: <tickets or parts, with the reason>
HOW TO START TONIGHT: <one command>
```
