---
id: 2026-11-27-04
date: 2026-11-27
version: 1
contract: "0.2"
target: opencode-build
tickets: []
status: ready
supersedes: null
---

# Ranking v3: the measures needed to write the next plan (read-only, no build)

Maintainer lines (filled when pasting):
```
TARGET A: <target> ; RUNS A: <every finished run with a triage file, and its triage replays> ; LYNCEUS REPORT A: <path>
TARGET B: <target> ; RUNS B: <same> ; LYNCEUS REPORT B: <path>
```

## Goal
The first result of ranking v3 is in: clearly closer to lynceus on one target, almost unchanged on the other, on a small number of pairs. What is left seems to come from the way preconditions are counted, but that is a reading of totals. The next plan must be written from measures, not from that reading.

This prompt builds nothing. It produces one document of tables, from outputs already stored, so that the plan can say for each change: which findings it moves, how many, and in which direction. No scan, no triage, no model call in any script. Where you have to judge by reading (M6 only), say so.

## Inputs
Branch `feat/ranking-v3` of both repositories, `docs/ranking-v3-facts.md`, the pairs file and the hand-check file of the previous prompt, the triage files of all runs and replays named above, the findings before triage of those runs, the lynceus reports with every field they hold, `reports/triage-single-session/REPORT.md` if it exists.

## Steps

Write everything in `docs/ranking-v3-measures.md`, one section per measure, in this order. Rules for every table:
- counts with their total (`n / N`), never a percentage alone;
- 15 rows at most; the rest goes in a row `other`;
- ids, families, levels and field names only: no finding text, no code, no path of the target;
- per target, and per run where the measure depends on the run;
- a value that is not stored is `not recorded`.

### M1. How many findings there are on each side
a. lynceus, per target: findings by hunt severity, and by proof status inside each severity.
b. lynceus, per severity: covered by a pair `same place`, by `covers`, by `mention only`, by nothing. Per run, and for the union of the runs of the target. This is the coverage by level; the top two levels matter most.
c. anduril, per run: confirmed findings by v2 severity and by v3 severity, each split in: has a pair, `mention only`, no pair.
d. The claim "no pair that lynceus rates critical is rated lower by v3": on how many pairs does it stand? If it is zero pairs, write it.
e. "Over-rated: 0": does that count include our HIGH and CRITICAL findings that have no pair? Give their number per run and by family.

### M2. Our level against theirs, in counts
For each target, the full table of our level against the highest lynceus level of the pair: once for v2, once for v3. Then the same two tables with the pairs `same place` only.

### M3. Factor by factor
lynceus writes its factors for each finding. If the report stores them (the rationale line or separate fields), parse them and compare on the pairs, one table per factor, our mapped value against theirs:
- reach;
- privileges and preconditions;
- impact;
- chaining.

Under each table: the share of pairs where the factor agrees, and the two most frequent disagreements. If lynceus stores several entry points with a reach for each: compare our reach with the reach of their most exposed entry point, and with the reach of the entry point that matches our primary place.

If the factors are not stored, say what is stored instead and stop M3 there.

### M4. What lowers each under-rated pair
For every pair where v3 is lower than lynceus:
a. the factor at which the tree stopped (reach, preconditions, impact, chaining, a value counted lower because unknown), against the number of levels of difference;
b. for those stopped by preconditions: their number of counted preconditions, and the kinds present.

### M5. Preconditions
a. Per run, all confirmed findings: number of preconditions by kind (`auth`, `config`, `victim`, `race`, `knowledge`, `chain`, `other`), and findings by number of counted preconditions.
b. On the pairs: for each kind, the lynceus level of the findings that hold at least one precondition of that kind, and of those that hold only that kind. It shows which kinds lynceus still rates high and which it rates lower.
c. On the pairs: lynceus level against our number of counted preconditions (0, 1, 2, 3, 4 and more).
d. The same finding in two runs or two triages (matched by rule: same file, same category, overlapping lines): how often the number of preconditions is the same, how often the set of kinds is the same.

### M6. What the preconditions say (the only part judged by reading)
Draw 40 preconditions of kind `other`, 20 of kind `knowledge` and 20 of kind `chain`, with a fixed seed, across all runs. Sort them by what they state, in six groups at most that you name (for example: repeats the access level already given by reach; a state of the application that normally holds; a second vulnerability; a value the attacker must know). Give the count of each group, and for each group one example rewritten in general terms, without any name of the target. Mark the section `judged by reading`.

### M7. Impact and chaining
a. Per run: confirmed findings by impact value; for `critical_asset_write`, how many name an asset.
b. The mapping used by v3 for impact, as implemented, one row per value of ours.
c. Number of findings with a `[chain]` precondition per run, over the confirmed findings of the run. If the share differs a lot between runs of the same target, say which setting, skill version or triage mode differs between those runs.

### M8. Simulations on the pairs (analysis script only; `ranking.py` is not changed)
Recompute the tables of M2 for each variant below. For each: same level, we are lower, we are higher, and the number of pairs that move against v3 as it is.

| variant | what changes |
|---|---|
| `v3` | nothing, the reference row |
| `strong-only` | preconditions are no longer counted: the finding is lowered only if it holds a strong one. One row per definition of strong: `config` ; `config, victim` ; `config, victim, race` ; `config, victim, race, knowledge` |
| `count-2` | counted as today, but one precondition does not lower |
| `no-other` | preconditions of kind `other` are not counted |
| `impact-limited` | our `limited` is read as a narrow impact, not as no gain |
| `impact-write` | `critical_asset_write` is read as a substantial impact, not as the first tier |
| `best` | the combination of the rows above that gives the fewest lower pairs without any higher pair on TARGET A |

Choose `best` on TARGET A only, then give its row for TARGET B. Both targets have been seen already: say so under the table, and give the number of pairs each row stands on.

### M9. Stability, on more findings
a. Three triages of the same findings where they exist (a run, its replays): findings confirmed by at least two of them; for each fact (reach, impact, number of preconditions, kinds of preconditions, chain or not), the share of findings where the triages agree; then the share with the same severity under v2, v3 and `best`.
b. The same vulnerability found by two different scans of a target (matched by the rule of M5d): the same table.

### M10. One anduril finding for several lynceus findings
On the pairs `same place` and `covers`: anduril findings by number of lynceus findings they cover (1, 2, 3 to 5, 6 and more); lynceus findings covered by more than one anduril finding; lynceus findings by number of entry points they store.

### M11. The top of lynceus that we do not cover
For the lynceus findings of the two highest levels that no pair covers, per target: by family; and for each, the furthest point it reached on our side in any run: a finding before triage in the same file and family (reported, then not confirmed), a finding before triage in the same file in another family, nothing.

### M12. Hand checks
- Where the file of 20 `covers` pairs is, and whether it was filled.
- Add to it 10 `mention only` pairs of TARGET A, drawn with a fixed seed, same columns, for the maintainer to mark as `same vulnerability` or not. It says how many real pairs hide in that class.

### M13. Reports already produced
Print, as they are, the `MEASURE`, `PHASES`, `SAME FINDINGS, THREE TRIAGES`, `CONTEXT`, `LEFT TO IMPROVE` and `VERDICT` blocks of the single-session triage report, and the `P2` line of the ranking v3 report. If the triage measure has not ended, write its state.

## Constraints
- Read-only on every run, replay and report. No scan, no triage, no model call in a script.
- `ranking.py`, the skills, the settings and the comparison rules are not changed. Variants live in the analysis script only.
- Analysis scripts in one folder of the branch, not called by the pipeline. One commit, subject `ranking-v3 measures`.
- Nothing is tuned and nothing becomes a default here.
- The document and the lists stay on this machine.

## Stop conditions
Stop and ask the maintainer when: the pairs file of the previous prompt is missing or cannot be rebuilt by rule; a measure would need a model call or a new run to be answered (skip it, mark it `needs a run`, go on with the others, and report at the end).

## Report
Under 40 lines, numbers only:
```
M1: lynceus by level <critical n, high n, ...> per target ; covered per level <pair n / N, mention only n / N> ; pairs with a lynceus critical <n> ; our HIGH and CRITICAL without pair <n per run>
M2: v3, per target: same <n / N> ; lower by 1 <n>, by 2 or more <n> ; higher <n>
M3: factors stored <yes | no> ; agreement: reach <n / N>, preconditions <n / N>, impact <n / N>, chaining <n / N> ; factor that disagrees most <name>, most frequent case <ours -> theirs>
M4: tree stopped by: reach <n>, preconditions <n>, impact <n>, chaining <n>, unknown <n>
M5: kinds that lynceus still rates high <list> ; rates lower <list> ; same number of preconditions between two triages <n / N>
M6: groups <name: n> (judged by reading)
M7: chain share per run <n / N each> ; reason of the difference <one line>
M8: per variant, A then B: same / lower / higher ; best = <combination>
M9: fact that agrees least between triages <name, n / N> ; same severity v2 <n / N>, v3 <n / N>, best <n / N>
M10: anduril findings covering 1 / 2 / 3-5 / 6+ lynceus findings <n each>
M11: top two lynceus levels not covered <n> ; reported then not confirmed <n>, other family <n>, nothing <n>
M12: hand-check file <path>, filled <yes | no>
M13: <the blocks, or the state of the measure>
NEEDS A RUN: <measures skipped, or none>
DISAGREEMENTS: <points of this prompt you think are wrong, with evidence, or none>
```
