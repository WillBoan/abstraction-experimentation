"""Compare a governance ARM against the batch of record, member for member.

The arm changes only the learn-side metric, so:

  1. Every CHAIN cell must be untouched -- same certificate, same top-chain reachability. That is
     the wiring assertion (S15's method): if the certificate moves, the arm changed something it
     had no business changing and its learnability readings mean nothing.
  2. What may move is RECOVERY, and the diagnosis says whether a miss is proposer reach
     (`not-proposed`) or governance preference (`proposed-not-selected`).

Usage: uv run python arm_vs_record.py <record.json> <arm.json>
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    record = {m["name"]: m for m in json.load(open(sys.argv[1]))}
    arm = {m["name"]: m for m in json.load(open(sys.argv[2]))}
    names = sorted(set(record) & set(arm))

    print(f"{len(names)} members compared\n")

    # --- 1. the wiring assertion
    moved = [
        n
        for n in names
        if (record[n]["admitted"], record[n]["top_chain"]) != (arm[n]["admitted"], arm[n]["top_chain"])
    ]
    print("## Wiring assertion: a learn-side change must move NO chain cell")
    print(f"   members whose certificate or chain-top moved: {len(moved)} {moved}")
    print("   (non-zero here invalidates everything below)\n")

    # --- 2. recovery
    print("## Rung recovery: record -> arm")
    header = f"{'ladder':30} {'record':>8} {'arm':>8}  diagnosis (arm)"
    print(header)
    print("-" * len(header))
    collapsed, held, na = [], [], []
    for n in names:
        r, a = record[n], arm[n]
        if not r["rungs_total"]:
            na.append(n)
            continue
        rr = f"{r['rungs_recovered']}/{r['rungs_total']}"
        aa = f"{a['rungs_recovered']}/{a['rungs_total']}"
        diag = ", ".join(a["diagnoses"]) or "-"
        flag = ""
        if a["rungs_recovered"] < r["rungs_recovered"]:
            collapsed.append(n)
            flag = "  <-- LOST"
        elif a["rungs_recovered"] == r["rungs_recovered"] and r["rungs_recovered"] > 0:
            held.append(n)
        print(f"{n:30} {rr:>8} {aa:>8}  {diag}{flag}")

    tot_r = sum(record[n]["rungs_recovered"] for n in names)
    tot_a = sum(arm[n]["rungs_recovered"] for n in names)
    tot_n = sum(record[n]["rungs_total"] for n in names)
    print(f"\n   TOTAL rungs recovered: {tot_r}/{tot_n} (record) -> {tot_a}/{tot_n} (arm)")
    print(f"   members losing recovery: {len(collapsed)}")
    print(f"   members holding recovery: {len(held)} {held}")
    print(f"   members with no rungs to recover (rejected/no climb): {len(na)}")

    # --- 3. why
    print("\n## Why the arm missed, by mechanism")
    counts: dict[str, int] = {}
    for n in names:
        for d in arm[n]["diagnoses"]:
            counts[d] = counts.get(d, 0) + 1
    for diag, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"   {diag:24} {count} members")
    print(
        "\n   `proposed-not-selected` = the proposer OFFERED a behavioural match and governance\n"
        "   declined it. Under a two-part code that charges definition size, declining is the\n"
        "   DL-optimum when too few programs share the abstraction -- so this is the learner\n"
        "   being right, not failing."
    )

    # --- 4. cost
    print("\n## Wall clock")
    print(f"   record: {sum(record[n]['seconds'] for n in names)/60:.1f} min")
    print(f"   arm:    {sum(arm[n]['seconds'] for n in names)/60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
