---
id: 2026-11-27-03
date: 2026-11-27
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: draft
supersedes: null
---

# Why two scans of the same code differ, and what gap-fill really adds

Maintainer lines (filled when pasting):
```
TARGET A: <target> ; RUN 1: <finished full scan> ; RUN 2: <another finished full scan of the same code>
LYNCEUS REPORT A: <path>
SCAN RUNS: <go | wait>
```

## Goal
Two scans of the same target share only a part of their findings, and their union covers clearly more of lynceus than the better of the two. Before gap-fill is changed, the place where a finding is lost has to be known. There are four, and each has another fix:

| where it is lost | fix it points to |
|---|---|
| the file is in no zone | zone generation, or zones stored and reused |
| the file is in a zone, the unit did not read it | coverage inside a unit, gap-fill driven by what was not read |
| the file was read, nothing was reported | the model: a second pass, or a pass that asks one question across the code |
| it was reported, triage did not confirm it | triage (verdict, duplicate, `untriaged`), not the scan |

Part 1 answers from runs that already exist, in Python, without a model. Part 2 adds two runs of the scan stage alone. Part 3 is a proposal: nothing is built on gap-fill in this prompt. Argue with evidence where you disagree.

## Inputs
The directories of `RUN 1` and `RUN 2` (zone definitions, session logs, findings before triage, `COVERAGE.json`, triage file, resolved settings), the lynceus report, the comparison tool, the gap-fill code and its settings.

## Steps

## Part 1 — attribution from existing runs (Python, no model call)

Write the tables in `docs/scan-differences-facts.md`. A value the runs did not store is `not recorded`.

### V1. The two runs side by side
- Settings that differ between the two runs, and the code version of each. A difference that comes from the settings is not variance; name it.
- Zones: number, files per zone; share of files that are in a zone in both runs, in one only, in none.
- Files really read by the units, from their own tool calls: read in both runs, in one only, in none. Split by kind of file where the kind is known from the path (entry points, access control, data access, other).
- Findings before triage, matched by rule and never by a model's judgement:

| class | rule |
|---|---|
| same | same file, same category, overlapping lines |
| moved | same file, same category, other lines |
| same file | same file, other category |
| only in one | no match |

- The same counts for findings confirmed by triage.

### V2. Each finding found by one run only
For every finding before triage that is `only in one`, look in the other run:
- `not in a zone`: its file was in no zone;
- `not read`: its file was in a zone, no unit read it;
- `read, not reported`: a unit read the file and reported nothing there.

For every finding that both runs reported and only one confirmed: `other verdict`, `duplicate of another finding`, `untriaged`.

One table: cause against count, with the share of each cause.

### V3. Each lynceus finding that was missed
For the lynceus findings covered by neither run, then for those covered by one run only, the same causes: `not in a zone`, `not read`, `read, not reported`, `reported, not confirmed`, `reported in another family`. One table, family against cause. It says, for the families lynceus finds and anduril misses, whether the code was never read or was read and judged fine.

### V4. Gap-fill as it is
- How gap-fill chooses its zones today: its inputs, who decides (the model or a rule), the cap.
- For each of the two runs that used it, base zones against gap-fill zones: findings before triage, confirmed, lynceus findings covered that no base zone covered, tokens, duration. Then the cost in tokens of one more confirmed finding and of one more lynceus finding covered, base against gap-fill.
- Files read by gap-fill units that a base unit had already read.

### Conclusion of Part 1
Three lines under the tables: the cause that weighs most in V2; the cause that weighs most in V3; whether gap-fill zones go where V2 and V3 say findings are lost.

## Part 2 — two runs of the scan stage alone (only if `SCAN RUNS: go`, scheduler free)

The scan stage only: the pipeline stops before triage. If no option does it, add `--until scan`. Same settings as `RUN 2`.

| run | zones | compared with `RUN 2` it shows |
|---|---|---|
| `same zones` | the zone definitions stored by `RUN 2`, reused as they are | the variance of the agents alone |
| `new zones` | generated again | the variance of the agents and of zone generation together |

For each: the match table of V1 against `RUN 2`, before triage; the causes of V2; lynceus findings reported before triage (an upper bound of coverage, said as such). Then the union of two and of three runs: lynceus findings reported, and tokens spent, so that one more pass can be compared with gap-fill at the same cost.

Through last night's launcher, detached, one run at a time, each with a predicted duration and a time limit of twice the prediction.

## Part 3 — proposal, one page, nothing built
From the tables, for each option: what it would change, the gain to expect with the number it comes from, its cost.
- Zones generated at each scan, or stored for a revision of the target and reused.
- Gap-fill fed by facts (files not read, entry points not reached) instead of the model's own view of what is missing.
- A pass by question instead of by code area, for the families of V3 where the code was read and nothing was reported (one question followed across all entry points).
- One more full pass against gap-fill, at equal tokens.

## Constraints
- Part 1 reads stored outputs and never modifies them.
- The only code allowed: the analysis scripts, `--until scan`, and reuse of stored zones if it is missing; both behind options whose default is today's behaviour.
- No change to zone generation, gap-fill, the scan skill or triage.
- A running scan or replay that is not part of this work is not touched; Part 2 waits for the scheduler to be free.
- One commit per part, subject `scan-diff <part>: <what>`.
- Results stay on this machine.

## Stop conditions
Stop and ask the maintainer when: `SCAN RUNS` is `wait` (do Part 1, then report); the runs did not store the files read by each unit and they cannot be rebuilt from the session logs; the two runs were not made on the same revision of the target.

## Report
```
V1: settings that differ <list> ; files in a zone in both <x %>, one <x %>, none <x %> ; files read in both <x %>, one <x %>, none <x %> ; findings before triage: same <n>, moved <n>, same file <n>, only in one <n> ; confirmed: <same four counts>
V2: not in a zone <x %> ; not read <x %> ; read, not reported <x %> ; lost in triage: other verdict <n>, duplicate <n>, untriaged <n>
V3: <family: not in a zone, not read, read not reported, not confirmed, other family> for the five largest families
V4: gap-fill chooses by <rule | model>, from <inputs> ; base / gap-fill: findings <n / n>, confirmed <n / n>, lynceus findings only it covers <n / n>, tokens per confirmed finding <n / n>
CONCLUSION: <three lines>
PART 2: same zones: same <n>, only in one <n> ; new zones: same <n>, only in one <n> ; union of 2 runs <lynceus findings reported>, of 3 <n> ; or not run
PROPOSAL: <one line per option: gain, cost>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
