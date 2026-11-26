---
id: 2026-11-26-06
date: 2026-11-26
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: ready
supersedes: 2026-11-26-03
---

# Facts for a future scan control script and for waking opencode on an event (nothing is built)

Maintainer lines (filled when pasting):
```
SCANNER REPO: <path>
ORCHESTRATOR REPO: <path>
LAST NIGHT'S QUEUE: <path of its script, its state file and its log>
```

## Goal
You start without context. Two tools exist: a scanner (anduril) and its orchestrator (andurilctl), in two repositories. Scans are launched one after the other by a batch script, and last night no scan of the queue finished: nobody was there to notice.

Later, one control script will live with the orchestrator and centralise the state and the logs of every scan; it may wake an opencode session when something needs judgement. The existing batch and watch scripts will then be removed, so nothing new is added to them now. This prompt only collects the facts needed to specify that control script. **You write no code and change no file in either repository.**

## Inputs
The two repositories (read-only), the queue files named above, the run directories of past scans, `opencode --help` and `opencode run --help` on this machine.

## Steps

### F1. Last night
From the logs only: which process stopped first, at what time, with which traceback or signal; what each queued scan did after that (never started, started and failed at which stage, still running); what the state file says now, and whether it is true.

### F2. What launches and watches scans today
Every script, in both repositories and next to them, that launches, queues, resumes or watches scans. One row each: path; what it does in one line; who starts it; which state it writes and where; whether it survives the end of the terminal session; your verdict `keep`, `replace by the control script` or `dead`.

### F3. Where the state of a scan lives
For one scan from submission to final report, every place where its state or its logs are written: orchestrator queue, run directory, per-stage logs, metrics files, model session logs, sandbox or container logs. One row each: path pattern, format, written by which process, at which moment. Then the list of questions that cannot be answered today from one place, among: what is every scan doing now; at which stage and since when; which settings it really received; did it fail and why; how many tokens and how long per stage.

### F4. What the orchestrator already offers
Its commands and their output formats (queue, status, cancel and the others); whether it has its own loop or daemon; how a script can learn that a scan ended or failed without reading logs (exit code, state file, hook, event); what it does with a scan that fails; what it does when its own process stops.

### F5. opencode without a person
Do the tests in an empty temporary directory outside both repositories, with a harmless prompt.
- Version, and the options of `opencode run` copied as printed by `--help`.
- Can a session be started non-interactively with a chosen agent and a chosen model? Exact command. Does it end by itself, and with which exit code?
- What happens in that mode when an action is on "ask": does the session wait forever, refuse, or go on?
- Can one agent be denied every edit and limited to a list of shell commands? Show the configuration used and the refusal obtained.
- Where the logs of such a session are written.
- Is there a built-in way to repeat or schedule a prompt? Answer from `--help` and the installed documentation, not from memory.

### F6. Proposal, text only, one page at most
- The central record of a scan: its fields (label, target, model, settings received, stage, start and end of each stage, status, failure reason, paths of its logs).
- Where the control script lives in the orchestrator and which existing commands it uses.
- The events it would raise (queue stopped, scan failed, scan without progress, settings differ from what was asked) and, for each, what a script can do alone and what needs a model.
- What becomes dead code once it exists.
- What you would do differently, with your reasons.

## Constraints
- Read-only on both repositories and on every run directory. The only files you create are in the temporary directory of F5 and the report file below.
- No scan is started, stopped, re-submitted or modified. No process of a running scan or queue is touched.
- "Not found" and "not recorded" are valid answers; a guess is not.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: answering a point would require changing a file in a repository or touching a running process; the queue files of last night are not at the paths given.

## Report
Write the full answers in `scan-control-facts.md` in the temporary directory, and print this summary, short enough for two screens:
```
LAST NIGHT: <process> stopped at <time> ; cause <one line> ; scans: <label: what happened>
SCRIPTS: <n> found ; keep <names> ; replace <names> ; dead <names>
STATE: written in <n> places ; cannot be answered from one place today: <questions>
ORCHESTRATOR: end of scan known by <mechanism> ; failed scan <behaviour> ; own stop <behaviour>
OPENCODE: non-interactive <yes, command | no> ; ends by itself <yes|no> ; on "ask" <behaviour> ; edits denied for one agent <yes|no> ; built-in schedule <yes|no>
PROPOSAL: <five lines at most>
FULL ANSWERS: <path>
```
