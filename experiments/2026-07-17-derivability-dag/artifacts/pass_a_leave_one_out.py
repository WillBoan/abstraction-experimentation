"""Pass A: leave-one-out derivability over the full monomorphic library.

For each target primitive T, enumerate compositions over ALL_MONO - {T} and find
the minimal behavioral derivation of T. Output: the derivability table + the
"uses" DAG edges (T -> support of its minimal witnesses).

Run:  uv run python experiments/2026-07-17-derivability-dag/artifacts/pass_a_leave_one_out.py \
        2>&1 | tee experiments/2026-07-17-derivability-dag/artifacts/pass_a_leave_one_out.out
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from enumlib import (  # noqa: E402
    enumerate_pool,
    find_derivations,
    mono_blocks,
    target_valid_count,
)

MAX_SIZE_DEFAULT = 3
MAX_SIZE_UNARY_GRID = 4  # (grid,)->grid is cheap; go one deeper


def main() -> None:
    blocks = mono_blocks()
    print(f"{len(blocks)} monomorphic blocks: {', '.join(sorted(blocks))}\n", flush=True)

    results: dict[str, dict] = {}
    for name in sorted(blocks):
        target = blocks[name]
        others = {n: b for n, b in blocks.items() if n != name}
        max_size = (
            MAX_SIZE_UNARY_GRID
            if target.param_types == ("grid",) and target.return_type == "grid"
            else MAX_SIZE_DEFAULT
        )
        if target_valid_count(target) < 6:
            print(f"{name:20s} SKIP (too few valid sample tuples)", flush=True)
            results[name] = {"status": "skip"}
            continue
        t0 = time.time()
        pool = enumerate_pool(others, target.param_types, max_size)
        found = find_derivations(target, pool, others)
        dt = time.time() - t0
        if found is None:
            print(f"{name:20s} SKIP (too few valid sample tuples)  [{dt:.1f}s]", flush=True)
            results[name] = {"status": "skip"}
            continue
        derivs, n_valid = found
        meta = f"[{dt:5.1f}s, {pool.n_terms} terms{', TRUNC' if pool.truncated else ''}, {n_valid} valid]"
        if not derivs:
            print(f"{name:20s} none <= size {max_size}  {meta}", flush=True)
            results[name] = {"status": "underivable", "max_size": max_size,
                             "truncated": pool.truncated}
            continue
        d0 = derivs[0]
        flag = "" if all(d.verified for d in derivs) else "  !! HOLDOUT-UNVERIFIED"
        print(f"{name:20s} size {d0.size}: {d0.term}{flag}  {meta}", flush=True)
        for d in derivs[1:]:
            print(f"{'':20s}   also: {d.term}{'' if d.verified else '  !! unverified'}", flush=True)
        results[name] = {
            "status": "derivable",
            "size": d0.size,
            "witnesses": [
                {"term": d.term, "support": list(d.support), "verified": d.verified}
                for d in derivs
            ],
            "truncated": pool.truncated,
        }

    out = Path(__file__).parent / "pass_a_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out}", flush=True)

    # DAG summary: edges from verified minimal witnesses only
    print("\n=== 'uses' DAG edges (target -> minimal-witness support) ===", flush=True)
    for name, r in sorted(results.items()):
        if r.get("status") == "derivable":
            supports = {p for w in r["witnesses"] if w["verified"] for p in w["support"]}
            if supports:
                print(f"  {name} <- {{{', '.join(sorted(supports))}}}", flush=True)


if __name__ == "__main__":
    main()
