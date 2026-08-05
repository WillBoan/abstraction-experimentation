# Curriculum-tax decomposition: what every climb actually spent, by class (2026-08-04)

A read-side investigation, zero new searches. The [tax-math notes](../../docs/abstraction_ladders/2026-07-29_chatgpt%20-%20tax%20math.md)
formalized the curriculum tax as a lower-rung / current-rung / higher-rung (LR/CR/HR)
decomposition with closed-form invocation counts. This asked: **what does that decomposition
actually look like on the 21 recorded climbs** — and it had a puzzle to resolve, because two
recorded facts made contradictory predictions about the split:

- per-iteration climb costs are nearly **flat** (`split-recolor-lean`: 32,665 / 32,837 / 33,009),
  suggesting iteration cost is dominated by one constant component;
- the 2026-07-23 **skip-solved** schedule arm saved **1.8–2.5x** by removing re-search of solved
  tasks, suggesting LR is roughly half the bill.

Both turn out to be right. The resolution is the finding.

## Method

[`artifacts/curriculum_decomposition.py`](artifacts/curriculum_decomposition.py) — output:
[`curriculum_decomposition.out`](artifacts/curriculum_decomposition.out) (summary tables) and
[`curriculum_decomposition.json`](artifacts/curriculum_decomposition.json) (per-member,
per-(task, wake) detail).

For every batch member with a committed `report.json`, follow `provenance` to the `climb/learn`
run dir and read `trace.jsonl`: per wake iteration, per task, `total.considered`,
`solutions.first_index`, and the solved list. Classify each (task, wake) search by **realized**
solve status: CR at its first-solve wake, HR before it, LR after it, **UN** if it never solves
in the climb (kept separate from HR — a task unreachable at *every* wake is a different defect
from a task attempted prematurely). Cost under two accountings from the same records:

- **actual** = `considered` (what the run paid under its own stop mode);
- **to-first** = `first_index + 1` where the search solved, `considered` otherwise — the
  counterfactual stop-at-first bill, exact because `first_solution_index` is stop-independent.

Caveats, stated up front: the classification is realized, not authored (no rung-assignment
join); the CR denominator below is the **climb's own** current-rung compute, not the oracle
chain's marginal (they nearly coincide on e.g. `split-recolor-lean`, 32.8k vs 35.8k, but are
different quantities); the to-first counterfactual ignores generation-end granularity. All 21
members' cells are single-generation (the 2026-08-04 re-baseline).

## Results

Store-wide, across all 21 climbs (19,456,316 considered total, actual accounting):

| class | spend | share |
| --- | --- | --- |
| CR — current-rung acquisition | 1,859,842 | **9.6%** |
| LR — re-search of acquired tasks | 2,139,513 | **11.0%** |
| HR — premature attempts (later solved) | 8,296,978 | **42.6%** |
| UN — never-solved tasks | 7,159,983 | **36.8%** |

**~80% of everything the climbs ever spent went to searches that could not succeed at the moment
they ran.** The UN mass is almost entirely the two known-broken `nor-halves` members
(`climb-budget-covers-top` class): each burns ~3.5M re-exhausting a depth-4-unreachable top every
wake — 99.9% of their climbs — and notably the unreachable top *exhausts its depth-3 space* at
~1.7–1.8M, below the 2M guard, so it is not even censoring.

### The puzzle resolved: the dominant class is an accounting-mode artifact

| segment | CR | LR | HR |
| --- | --- | --- | --- |
| 15 exhaustive-mode members, actual | 33.2% | **42.7%** | 20.8% |
| same members, to-first counterfactual | 34.5% | 5.6% | **56.0%** |
| 4 healthy stop-at-first members, actual | 10.1% | 7.4% | **82.6%** |

Under the batch's default `solution_limit=None` generation-end accounting, a solved task's
re-search still exhausts its depth-limited space — so every task pays roughly the same per wake
regardless of class. That is why iterations are flat (cost ≈ n_tasks x per-task exhaustion,
creeping up ~0.5%/wake with mints), and why LR is the largest slice (~43%), which is exactly what
skip-solved's 1.8–2.5x was collecting. Under stop-at-first, re-finds are nearly free and the same
members' split inverts to HR-dominated. The two `nor-recolor` members (5-wake, stop-first)
measure **69.8% / 71.0% HR share** — the tax-math notes' worked example (70%) realized in the
store. Consequence, now demonstrated rather than advised: **cross-member curriculum-tax
comparisons must stratify by accounting mode.**

### The premature-top cell is the single dominant cost on d3-top members

`split-asym-lean` wake 0: the top, attempted before any rung exists, censors at exactly
**2,000,000**; one wake later, post-mint, the same top solves for **64,178**. `split-halves-lean`:
2,000,000 vs **62,040**. One badly-timed search is **31x** the eventual useful work, and it puts
those members' full-vs-CR multipliers at **13.4x / 32.9x** — where the all-d2 members sit at
3.0–4.0x (this script's M reproduces the recorded loop-overhead factors on those members). The
recorded "loop overhead is 3–4x" was measured only on the schedule shape that minimizes it.

### The abstraction benefit is real but only a stop policy can cash it

LR drift ρ (re-search cost / that task's own CR cost), median per member:

- exhaustive members: **ρ ≈ 1.0–1.2** — re-search costs slightly *more* each wake as mints grow
  the space (up to 3.8 on tiny synthetic spaces: `al1`). BREADTH-AXIS C ("minting does not reduce
  search cost mid-climb") confirmed, per-member.
- stop-at-first members: **ρ ≈ 0.85–0.93** — re-finding is *cheaper* than the original solve,
  because the mint made the solution shallower (`first_index` drops).

Both opposing forces from the tax-math notes exist; **which wins is chosen by the stop policy,
not by the library.** Also measured in passing: solution churn is universal (every climbing
member rewrites every acquired task's retained program at least once — the post-mint
re-compression); zero solve regressions; invocation identities exact (every climb ran every task
every wake — early-stop cuts wakes, never within-wake tasks — so the closed-form N identities
apply with realized wake counts).

### The removable bill

A CR+LR schedule with to-first stopping — keep re-searching solved tasks (the recurrence
evidence), never attempt not-yet-reachable ones, stop when found — would have cost **2,141,733**
against the actual **19,456,316**: **9.1x of the total climb bill is removable by schedule and
stop policy alone** (per-member 1.9x–1716x; median ~7.7x; the extremes are the broken-top
members). Two caveats are part of the result: CR+LR requires knowing which tasks are reachable —
an oracle privilege, so this prices the curriculum-order prior rather than promising a blind
learner the discount — and to-first forfeits the exhaust-mode quantities (the standing
compromise trade).

## Decisions and follow-ups this sets up

1. **The CR+LR arm** is now the obvious next new-runs experiment, with registered predictions:
   mints byte-identical to the full schedule (sleep consumes solutions only; HR contributes
   none), savings per the table above. A confirmation makes "HR is deadweight, LR is the
   evidence" a measured statement.
2. **Mode stratification** is a demonstrated comparability wall, not advice; any renderer/report
   adoption of these metrics must carry it.
3. The **full-frozen replay cell** (full schedule against chain libraries, learning off) remains
   the missing cell for splitting overhead into direct tax vs learning effect.
4. Candidate metrics worth promoting into the ladder report: class shares (both accountings),
   M vs CR, ρ drift, churn count.

## Runs

One `climb/learn` run per member, resolved via each report's `provenance` (this investigation
read them; it wrote nothing):

| member | mode | wakes | climb/learn run |
| --- | --- | --- | --- |
| `94f9d214-nor-halves` | stop-first | 2 | [`8e85f48b2b91`](../../runs/2026-08-04/20260804_203853_8e85f48b2b9165b2/) |
| `94f9d214-nor-merged` | exhaustive | 4 | [`086d1d688536`](../../runs/2026-08-04/20260804_204303_086d1d6885366c2f/) |
| `94f9d214-nor-recolor` | stop-first | 5 | [`0988e459b009`](../../runs/2026-08-04/20260804_204319_0988e459b009d2bf/) |
| `al1-mirror` | exhaustive | 3 | [`c7dfd456076f`](../../runs/2026-07-22/20260722_212625_c7dfd456076ff761/) |
| `al12-unlearnable` | exhaustive | 1 | [`89868769ca0f`](../../runs/2026-08-03/20260803_201507_89868769ca0f82a3/) |
| `al15-shift-frame` | exhaustive | 3 | [`551e05c8a268`](../../runs/2026-08-03/20260803_203101_551e05c8a2682815/) |
| `al16-layout-nest` | exhaustive | 3 | [`40f4b8b641c2`](../../runs/2026-08-03/20260803_203107_40f4b8b641c27ffe/) |
| `al17-shift-frame-tall` | exhaustive | 4 | [`0efac0e88832`](../../runs/2026-08-03/20260803_203110_0efac0e88832553c/) |
| `al18-fanin-rotate` | exhaustive | 3 | [`8b85d26c47cb`](../../runs/2026-08-03/20260803_203118_8b85d26c47cbb3bc/) |
| `al19-fanin-recolor` | exhaustive | 3 | [`df41a6982550`](../../runs/2026-08-03/20260803_203122_df41a6982550d948/) |
| `al2-rot90-calibration` | exhaustive | 2 | [`35afb03c8453`](../../runs/2026-07-22/20260722_212647_35afb03c8453bd6d/) |
| `al20-recolor-telescope` | exhaustive | 3 | [`9a84ca44c492`](../../runs/2026-08-03/20260803_203141_9a84ca44c49201a7/) |
| `al21-dag-siblings` | exhaustive | 2 | [`2394300fc190`](../../runs/2026-07-26/20260726_204628_2394300fc1908dd5/) |
| `dae9d2b5-half-param` | exhaustive | 3 | [`e4e4de51d57e`](../../runs/2026-08-04/20260804_204715_e4e4de51d57e92d0/) |
| `dae9d2b5-split-asym-lean` | stop-first | 2 | [`be4030ec02ca`](../../runs/2026-08-04/20260804_204726_be4030ec02ca0843/) |
| `dae9d2b5-split-halves-lean` | stop-first | 2 | [`5c799e43ffce`](../../runs/2026-08-04/20260804_205018_5c799e43ffceb15b/) |
| `dae9d2b5-split-recolor` | exhaustive | 3 | [`487c5429df52`](../../runs/2026-08-04/20260804_205445_487c5429df52813b/) |
| `dae9d2b5-split-recolor-lean` | exhaustive | 3 | [`73adf3163f43`](../../runs/2026-08-04/20260804_210335_73adf3163f43e703/) |
| `fafffa47-nor-halves` | stop-first | 2 | [`ec9a6c359f3b`](../../runs/2026-08-04/20260804_210543_ec9a6c359f3bee50/) |
| `fafffa47-nor-merged` | exhaustive | 4 | [`85a670b006cc`](../../runs/2026-08-04/20260804_211056_85a670b006cc8638/) |
| `fafffa47-nor-recolor` | stop-first | 5 | [`cdb04726cab1`](../../runs/2026-08-04/20260804_211116_cdb04726cab17892/) |
