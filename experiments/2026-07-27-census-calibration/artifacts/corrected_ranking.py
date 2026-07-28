"""C9: the batch's round-1 breadth ranking, recomputed after the variadic fix.

The 2026-07-26 breadth-axis entry's headline was "it ranks the whole batch, and the OUTLIER is the
real-task ladder -- by 4x over the next worst", quoting `dae9d2b5/east` 1,212x and `/west` 1,211x
against `al13/sym_h` 278x. Those top two entries were inflated 9.24x by the `_slot_types` defect.

If the correction moves `dae9d2b5` below `al13`, the entry's headline is not merely off by a factor
-- it names the wrong outlier, and the ranking claim that the whole breadth-axis programme rests on
has to be restated from the corrected numbers rather than patched.

Static, whole-registry, no search.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder

rows: list[tuple[float, str, str, int, int]] = []
skipped: list[tuple[str, str]] = []

for name in sorted(ladder_paths()):
    try:
        spec = make_ladder(name)
        ctx = CheckContext(spec, corpus_backed=True)
        breadth = ctx.rung_breadth
    except Exception as exc:  # noqa: BLE001 - diagnostic sweep over the whole registry
        skipped.append((name, f"{type(exc).__name__}: {exc}"))
        continue
    if not breadth:
        skipped.append((name, "no corpus-backed breadth (no testbed?)"))
        continue
    for rb in breadth:
        if rb.ratio is None:
            continue
        rows.append((rb.ratio, name, rb.name, rb.b1_full, rb.b1_min))

rows.sort(reverse=True)

print("Round-1 breadth tax (b1_full / b1_min), worst first -- POST-FIX (2026-07-27)")
print(f"\n{'ratio':>10}  {'ladder':30} {'rung':18} {'b1_full':>8} {'b1_min':>7}")
print("-" * 80)
for ratio, ladder, rung, full, minimum in rows[:20]:
    print(f"{ratio:>9.1f}x  {ladder:30} {rung:18} {full:>8,} {minimum:>7,}")

print(f"\n... {len(rows)} rung readings total")
print("\nThe 1.0x floors (no constant battery at all):")
ones = [(l, r) for ratio, l, r, _, _ in rows if ratio == 1.0]
for ladder, rung in ones[:12]:
    print(f"    {ladder:30} {rung}")
print(f"    ({len(ones)} rungs read exactly 1.0x)")

if skipped:
    print(f"\nskipped {len(skipped)}:")
    for name, why in skipped:
        print(f"    {name:34} {why}")

print("\n" + "=" * 80)
print("The 2026-07-26 claim under test: is the real-task ladder still THE OUTLIER?")
print("=" * 80)
worst_ratio, worst_ladder, worst_rung, _, _ = rows[0]
print(f"  worst rung now: {worst_ladder} / {worst_rung} at {worst_ratio:.1f}x")
dae = [(ratio, l, r) for ratio, l, r, _, _ in rows if l.startswith("dae9d2b5")]
if dae:
    print(f"  worst `dae9d2b5` rung: {dae[0][1]} / {dae[0][2]} at {dae[0][0]:.1f}x")
    rank = next(i for i, (_, l, r, _, _) in enumerate(rows, 1) if l == dae[0][1] and r == dae[0][2])
    print(f"  its rank in the batch: {rank} of {len(rows)}")
