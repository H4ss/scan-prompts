---
id: 2026-11-27-02
date: 2026-11-27
version: 2
contract: "0.2"
target: opencode-build
tickets: []
status: applied
supersedes: null
---

# Ranking v3: lynceus' severity tree, computed in Python from our facts, judged pair by pair, without a new scan

Maintainer lines (filled when pasting):
```
SCANNER BRANCH: <branch that holds ranking v2 and the latest triage work>
TARGET A: <target used to tune> ; RUNS A: <finished anduril runs with their triage file> ; LYNCEUS REPORT A: <path>
TARGET B: <target used to check> ; RUNS B: <finished anduril runs> ; LYNCEUS REPORT B: <path>
```

## Goal
Your comparison of the two rankings is accepted as the starting point: lynceus lets its agent walk down a tree of four factors (reach, privileges and preconditions, impact, chaining) and stop at the first level that holds; anduril takes the lower of two axes, counts a chain as a precondition, and asks eight conditions for CRITICAL. The result is that anduril rates lower than lynceus on the same bug.

Direction, decided:
- keep what anduril has and lynceus has not: the agent states facts with evidence, Python computes the severity and writes why;
- compute lynceus' tree in Python from those facts, as ranking `v3`, behind a setting;
- not taken from lynceus: the proof-of-concept step (dynamic), and severity decided by the agent.

Two things your plan does not have yet, and that this prompt adds:

1. **The judge is the pair, not the distribution.** Two tools can show the same share of HIGH and disagree on every finding. v3 is judged on findings matched with lynceus findings, one pair at a time, and tuned on one target and checked on the other.
2. **One anduril finding often covers several lynceus findings** (lynceus reports one finding per entry point, anduril one finding for the common cause). That is the value of anduril, so the comparison must handle it: the severity of an anduril finding is compared with the highest severity among the lynceus findings it covers.

No scan, no triage replay, no model call in this prompt: everything is Python on stored outputs. Argue with evidence where you disagree.

## Inputs
`anduril/ranking.py` and its tests, `docs/ranking.md`, the triage skill (ranking phase, read-only), the triage files of `RUNS A` and `RUNS B`, the lynceus reports, lynceus' hunt prompt (read-only), the comparison tool of the scheduler repository.

The ranking code is in the scanner repository and the comparison tool in the scheduler repository: one branch `feat/ranking-v3` in each, each in its own worktree, and no worktree edits the other repository.

## Steps

### P1. Facts (read-only) in `docs/ranking-v3-facts.md`
a. **The tree of lynceus as a table**: one row per level, in the order the levels are tried, with the condition on each of the four factors, and the sentence that says what to do between two levels.
b. **Mapping, value by value**: each value of each lynceus factor, and the values of our facts that give it. Write `no equivalent` where our facts cannot tell (for example a reach that needs an action of a victim, which we hold as a precondition). "Same data, other combination" has to be shown on every line.
c. **Which lynceus severity is stored**: the one given by the hunt, the one after the proof-of-concept step, or both. A static scanner can only be compared with the first; if both exist, keep both.
d. **How the comparison tool matches today**: each kind of match, the rule behind it, whether a model takes part, and the count of each kind per run.
e. **Our facts as they are**, on all confirmed findings of the runs: share with `reach=unknown`, with no authentication evidence, with `impact=none`; number of findings by number of counted preconditions; number with a `[chain]` precondition.
f. **Several places in one finding**: when a finding covers several entry points or files, where are they recorded today (a field, the trace, free text)? For which place are reach and preconditions stated?

### P2. Pairs that can be trusted (Python, in the comparison tool)
One anduril finding against a set of lynceus findings. Three classes, by rule only:

| class | rule |
|---|---|
| `same place` | same file, overlapping lines, same family |
| `covers` | same family, and the file or entry point of the lynceus finding is one of the places our finding names as affected |
| `mention only` | our finding mentions the place of the lynceus finding, but in another family or not as an affected place |

- Families: one table that maps the categories of both tools to common families, kept with the comparison tool.
- `mention only` is not a pair. It is counted apart and never used for coverage or for severity.
- Output, local: one line per anduril finding with the lynceus findings it covers, the class, our severity, their severities and the highest of them.
- **Coverage restated**: lynceus findings covered by `same place`, by `covers`, by `mention only`, per run and for the union of the runs of a target. The coverage figure is the first two.
- **Hand check**: write 20 `covers` pairs of TARGET A, drawn with a fixed seed, to a local file (ids, family, files, titles) for the maintainer to mark right or wrong. Do not wait for it; report results for `same place` alone and for `same place` with `covers`.

### P3. Where v2 stands, before any change
On the pairs of each target, with our v2 severity against the highest lynceus severity of the pair:
- the table of our level against theirs;
- pairs where we are lower, by how many levels, by family;
- for each pair where we are lower: the rule of our trace that set the level (the reach side of the table, the count side, a missing condition of C1 and which one). One histogram. It puts numbers on your three mechanisms.
- the histogram of `critical_blockers` on our HIGH findings whose pair is critical for lynceus.

### P4. `derive_severity_v3` in `anduril/ranking.py`
Setting `stages.triage.ranking: v2 | v3`, default `v2`. v2 keeps its code path and its outputs.

- **The tree of P1a, on the mapping of P1b**, as a pure function. Same inputs as v2: no new fact is asked from the agent in this prompt.
- **The severity is the one lynceus' tree gives, nothing more.** The aim is that a finding lynceus rates critical is not rated lower by anduril because a proof is missing. Only an `unknown` or a value with `no equivalent` counts as the next lower value of its factor, and the trace says so: this is lynceus' own rule "between two levels, take the lower".
- **Chaining is the fourth factor.** A `[chain]` precondition leaves the count of preconditions and gives `chaining=chain-link`, with the effect the tree gives it.
- **CRITICAL**: the top of the tree and only it (remote without credentials, impact of the first tier, no counted precondition, standalone). The challenge of every candidate stays, with the effect lynceus gives to a failed proof of concept: a challenge that refutes a factor lowers the finding by one level; a missing proof lowers nothing.
- **Proofs become confidence.** New field `confidence: high | medium | low`, from the conditions that v2 used as blockers and that are proofs, not factors: authentication evidence present, production code path, verifier verdict `exploitable`, no dissenting vote, challenge survived. `high` when all hold, `low` when the authentication evidence or the verdict is missing, `medium` otherwise; `confidence_missing` lists what does not hold. Confidence never changes the severity; it orders findings inside a level, and the report shows a CRITICAL of low confidence as "to verify".
- **Outputs**: `severity`, `severity_rationale` in one line (`reach=...; privileges=...; impact=...; chaining=...`), `severity_trace`, `critical_blockers`, `confidence`.
- **Tests**: one case on each side of every limit of the tree; missing evidence lowers the factor; a chain is no longer counted as a precondition; property test over every combination of facts: CRITICAL only with the four conditions of the top of the tree and no refuted challenge; confidence never changes a severity; with `ranking: v2` the stored triage files give exactly the statistics they gave before.

### P5. v3 on stored findings
Recompute v3 on the triage files of `RUNS A` and `RUNS B`, from the facts as stored. A finding whose stored facts do not give a factor is `not computable` and counted; nothing is guessed.

Numbers, per target, v2 next to v3:
1. pairs with the same level; pairs within one level;
2. **under-rated**: pairs that lynceus rates critical or high and we rate medium or lower. This is the number v3 has to bring down;
3. **over-rated**: pairs we rate high or critical and lynceus medium or lower, and our high or critical findings with no pair. Listed by id, to be read by hand;
4. CRITICAL findings, each with its rationale line, its confidence and what is missing;
5. `not computable`, by missing factor.

Rules of tuning:
- thresholds and mapping are tuned on TARGET A only. TARGET B is computed once, at the end, and reported as it comes;
- no value is tuned to make the two distributions look alike;
- every value changed after the first v3 result is listed with the number it moved.

**Stability**: for findings that were triaged more than once (a run and its triage replays), share with the same severity across the triages, under v2 and under v3. A formula that follows the facts more closely can also follow their noise; this says whether it does, and which fact changes most between two triages.

### P6. Proposal, not built
From P1f and P5, one page in `docs/ranking-v3-facts.md`:
- what the ranking agent would have to state that it does not state today (for example the list of places a finding covers, and the facts for the most exposed of them), with the number of findings it would change;
- the facts whose instability moves severities, and what would steady them.

## Constraints
- No scan, no triage, no model call. Stored outputs are read, never modified.
- No change to the scan skill, the triage skill or the ranking prompt.
- Default stays `v2` until the maintainer has read the under-rated and over-rated lists.
- Zero CRITICAL is a valid result. No value is changed to obtain one.
- The number to watch first: pairs that lynceus rates critical and v3 rates lower. Each one is listed with the factor that lowered it.
- One commit per part, subject `ranking-v3 <part>: <what>`.
- Results, pairs and lists stay on this machine.

## Stop conditions
Stop and ask the maintainer when: the lynceus report holds no severity that can be read per finding; fewer than 20 pairs of the classes `same place` and `covers` exist on TARGET A; the tree needs a fact that no stored finding holds, so that most findings are `not computable`.

## Report
```
P1: tree levels <n> ; values with no equivalent <list> ; lynceus severity stored <hunt | after proof | both> ; match kinds today <kind: rule or model, count> ; reach unknown <x %> ; no authentication evidence <x %> ; places of a finding recorded in <where>
P2: per target: same place <n> ; covers <n> ; mention only <n> ; coverage <same place %, with covers %, union of runs %> ; hand-check file <path>
P3: per target: same level <x %> ; we are lower <x %>, higher <x %> ; rule that set the level when lower <histogram> ; C1 conditions blocking pairs critical for lynceus <histogram>
P4: tests <passed/total> ; v2 unchanged <proof>
P5: per target, v2 / v3: same level <x / x> ; within one level <x / x> ; under-rated <n / n> ; over-rated <n / n> ; CRITICAL candidates <n / n> ; not computable <n> ; values tuned <list with the number each moved>
STABILITY: same severity across triages v2 <x %>, v3 <x %> ; fact that changes most <name>
P6: <three lines at most>
VERDICT: v3 <better on both targets | better on A only | not better>, because <one line>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
