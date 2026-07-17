"""Shared typed bottom-up enumerator over primitive impls (derivability probes).

Throwaway probe library for the 2026-07-17 derivability-DAG investigation.
Enumerates compositions of ``BASE_PRIMITIVES`` impls over typed ``Param`` leaves,
dedups by observational equivalence on a fixed deterministic sample battery, and
answers: *is target primitive T behaviorally derivable over block set B, and at
what minimal size (application count)?* — with held-out verification (the E13
transpose/rot180 collision is the cautionary tale).

This is NOT the search engine: it measures compositional structure (static jump
depths and witnesses), not engine search cost. No RNG anywhere (repo convention).

Scope (v1, noted in the notebook):
- Monomorphic, first-order primitives only. Excluded as both blocks and targets:
  function-typed / body-sampler primitives (build_grid, map, filter, fold,
  sort_by), polymorphic ones (eq, if, pair, fst, snd, head, length, zip, shape),
  ``identity`` (dominated by the bare Param leaf), and ``tile`` (variadic with a
  rows*cols arity coupling). ``overlay`` is instantiated at 2 trailing grids.
- No constant leaves: a derivation must route every Color/Int through the
  target's own parameters or a perceiver. (Constants would let literal cheats
  shadow structural derivations — the E11 cheapest-wins trap, statically.)
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.core.mask import Mask
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import TypeCon

ERR = "<ERR>"  # evaluation-failure sentinel (string: cheap, hashable, unambiguous here)

# ---------------------------------------------------------------------------
# Block model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Block:
    name: str
    param_types: tuple[str, ...]
    return_type: str
    fn: Callable[..., Any]


EXCLUDED = {
    # function-typed / lambda-synthesis
    "build_grid", "map", "filter", "fold", "sort_by",
    # polymorphic (type vars) or pair-typed
    "eq", "if", "pair", "fst", "snd", "head", "length", "zip", "shape",
    # dominated by the bare Param leaf
    "identity",
    # variadic with rows*cols arity coupling
    "tile",
}


def _type_key(t: Any) -> str | None:
    """String key for supported monomorphic types; None if unsupported."""
    if isinstance(t, TypeCon):
        if not t.args:
            return t.name
        if (
            t.name == "list"
            and len(t.args) == 1
            and isinstance(t.args[0], TypeCon)
            and t.args[0].name == "color"
            and not t.args[0].args
        ):
            return "list[color]"
    return None


def mono_blocks() -> dict[str, Block]:
    """Every usable monomorphic primitive as a Block (overlay fixed at 2 grids)."""
    blocks: dict[str, Block] = {}
    for name, prim in sorted(BASE_PRIMITIVES.items()):
        if name in EXCLUDED or prim.body_sampler is not None:
            continue
        keys = [_type_key(t) for t in prim.param_types]
        ret = _type_key(prim.return_type)
        if any(k is None for k in keys) or ret is None:
            continue
        if prim.variadic_param is not None:
            if name == "overlay":  # (color, *grid) -> fixed (color, grid, grid)
                impl = prim.impl
                blocks[name] = Block(
                    name, ("color", "grid", "grid"), "grid",
                    lambda c, a, b, _f=impl: _f(c, a, b),
                )
            continue
        blocks[name] = Block(name, tuple(k for k in keys if k), ret, prim.impl)
    return blocks


# ---------------------------------------------------------------------------
# Deterministic sample battery
# ---------------------------------------------------------------------------


def _pat(h: int, w: int, ar: int, ac: int, off: int, mod: int = 10) -> Grid:
    return Grid(
        np.array(
            [[(r * ar + c * ac + off) % mod for c in range(w)] for r in range(h)],
            dtype=np.int8,
        )
    )


def _accent(bg: int, a: int, b: int) -> Grid:
    return Grid.from_list([[a, bg, bg], [bg, bg, bg], [bg, bg, b]])


# Shapes deliberately aligned index-by-index between the grid and mask pools, so
# aligned tuples give shape-valid (grid, mask) pairs.
PRIMARY_GRIDS: list[Grid] = [
    _pat(3, 3, 1, 2, 0),                      # asymmetric pattern, all-distinct-ish
    _accent(3, 1, 2),                          # clear background 3
    _pat(2, 3, 2, 1, 1, 6),                    # non-square, small palette
    Grid.from_list([[4, 7, 4], [4, 4, 9]]),    # 2x3, bg 4
    _pat(3, 3, 2, 5, 3),                       # second asymmetric pattern
    Grid.from_list([[1, 0], [0, 2]]),          # 2x2
]
HOLDOUT_GRIDS: list[Grid] = [
    _pat(3, 3, 1, 2, 5),
    _accent(6, 5, 9),
    _pat(2, 3, 1, 4, 2, 7),
    Grid.from_list([[8, 8, 1], [8, 2, 8]]),
    _pat(3, 3, 4, 7, 1),
    Grid.from_list([[3, 5], [5, 4]]),
]
# All masks 3x3 and pairwise set-incomparable (no m_i subset of m_j), so binary
# mask ops never degenerate to a projection on the sampled pairs. (grid, mask)
# targets then only get valid instances on the 3x3 grids — acceptable; the
# holdout battery guards against shape-specific coincidences.
PRIMARY_MASKS: list[Mask] = [
    Mask.from_list([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
    Mask.from_list([[0, 1, 0], [1, 0, 1], [0, 1, 0]]),
    Mask.from_list([[1, 1, 0], [0, 0, 1], [1, 0, 0]]),
    Mask.from_list([[0, 0, 1], [1, 1, 0], [0, 1, 1]]),
    Mask.from_list([[1, 1, 0], [1, 0, 0], [0, 0, 0]]),  # corner: sub-grid bbox
    Mask.from_list([[0, 0, 0], [0, 0, 1], [0, 1, 1]]),  # corner: sub-grid bbox
]
HOLDOUT_MASKS: list[Mask] = [
    Mask.from_list([[1, 1, 1], [0, 0, 0], [1, 0, 1]]),
    Mask.from_list([[0, 0, 0], [1, 1, 1], [0, 1, 0]]),
    Mask.from_list([[1, 0, 0], [0, 0, 1], [0, 1, 1]]),
    Mask.from_list([[0, 1, 1], [1, 1, 0], [0, 0, 0]]),
    Mask.from_list([[0, 1, 1], [0, 0, 1], [0, 0, 0]]),  # corner: sub-grid bbox
    Mask.from_list([[0, 0, 0], [1, 0, 0], [1, 1, 0]]),  # corner: sub-grid bbox
]

PRIMARY_POOLS: dict[str, list[Any]] = {
    "grid": PRIMARY_GRIDS,
    "mask": PRIMARY_MASKS,
    "color": [0, 1, 2, 3, 5, 7],
    "int": [1, 2, 0, 3, 1, 2],
    "bool": [True, False, False, True],  # 4 entries so strided pairs hit all combos
    "list[color]": [[1, 2, 3], [0, 5, 0, 5], [2, 2, 2], [7, 8]],
}
HOLDOUT_POOLS: dict[str, list[Any]] = {
    "grid": HOLDOUT_GRIDS,
    "mask": HOLDOUT_MASKS,
    "color": [4, 6, 9, 1, 8, 0],
    "int": [2, 3, 1, 0, 2, 1],
    "bool": [False, True, True, False],
    "list[color]": [[9, 4], [1, 1, 6], [0, 3, 0, 3], [5]],
}

_STRIDES = (1, 2, 3, 5, 7)  # per-position strides for the non-aligned tuples

N_PRIMARY = 16
N_HOLDOUT = 8


def sample_tuples(leafsig: tuple[str, ...], pools: dict[str, list[Any]], n: int) -> list[tuple[Any, ...]]:
    """Deterministic argument tuples for a leaf signature.

    The first ``len(min pool)`` tuples are index-aligned across positions (so
    shape-coupled pairs like (grid, mask) or (grid, grid) get valid instances);
    the rest stride each position by a distinct prime for diversity.
    """
    tuples: list[tuple[Any, ...]] = []
    aligned = min(len(pools[t]) for t in leafsig) if leafsig else 0
    for i in range(n):
        vals = []
        for j, t in enumerate(leafsig):
            pool = pools[t]
            if i < aligned:
                vals.append(pool[i % len(pool)])
            else:
                vals.append(pool[(i * _STRIDES[j % len(_STRIDES)] + j) % len(pool)])
        tuples.append(tuple(vals))
    return tuples


def canonical(v: Any) -> Any:
    """Hashable canonical form of a runtime value."""
    if isinstance(v, (Grid, Mask)):
        return v
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (list, tuple)):
        return tuple(canonical(x) for x in v)
    return v


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------
# term := ("P", i)  |  ("A", block_name, (child_term, ...))


def term_str(term: tuple[Any, ...]) -> str:
    if term[0] == "P":
        return f"p{term[1]}"
    return f"{term[1]}({', '.join(term_str(c) for c in term[2])})"


def term_size(term: tuple[Any, ...]) -> int:
    if term[0] == "P":
        return 0
    return 1 + sum(term_size(c) for c in term[2])


def term_support(term: tuple[Any, ...]) -> frozenset[str]:
    if term[0] == "P":
        return frozenset()
    out = frozenset({term[1]})
    for c in term[2]:
        out |= term_support(c)
    return out


def eval_term(term: tuple[Any, ...], args: tuple[Any, ...], blocks: dict[str, Block]) -> Any:
    if term[0] == "P":
        return args[term[1]]
    vals = []
    for c in term[2]:
        v = eval_term(c, args, blocks)
        if v is ERR or v == ERR:
            return ERR
        vals.append(v)
    try:
        return blocks[term[1]].fn(*vals)
    except Exception:
        return ERR


# ---------------------------------------------------------------------------
# Bottom-up enumeration with observational-equivalence dedup
# ---------------------------------------------------------------------------


@dataclass
class EnumResult:
    """seen[type] -> {signature: (size, term)} over the primary battery."""

    seen: dict[str, dict[tuple[Any, ...], tuple[int, tuple[Any, ...]]]]
    tuples: list[tuple[Any, ...]]
    truncated: bool
    n_terms: int


def enumerate_pool(
    blocks: dict[str, Block],
    leafsig: tuple[str, ...],
    max_size: int,
    *,
    max_combos_per_prim_size: int = 60_000,
    max_pool_per_type: int = 4_000,
) -> EnumResult:
    tuples = sample_tuples(leafsig, PRIMARY_POOLS, N_PRIMARY)
    # by_size[s][type] -> list of (term, vector)
    by_size: list[dict[str, list[tuple[tuple[Any, ...], tuple[Any, ...]]]]] = [
        {} for _ in range(max_size + 1)
    ]
    seen: dict[str, dict[tuple[Any, ...], tuple[int, tuple[Any, ...]]]] = {}
    truncated = False
    n_terms = 0

    def add(size: int, typ: str, term: tuple[Any, ...], vec: tuple[Any, ...]) -> None:
        nonlocal n_terms, truncated
        if all(v == ERR for v in vec):
            return
        bucket = seen.setdefault(typ, {})
        if vec in bucket:
            return
        if len(bucket) >= max_pool_per_type:
            truncated = True
            return
        bucket[vec] = (size, term)
        by_size[size].setdefault(typ, []).append((term, vec))
        n_terms += 1

    for i, typ in enumerate(leafsig):
        vec = tuple(canonical(t[i]) for t in tuples)
        add(0, typ, ("P", i), vec)

    for s in range(1, max_size + 1):
        for bname in sorted(blocks):
            blk = blocks[bname]
            k = len(blk.param_types)
            if k == 0:
                continue
            combos = 0
            # child sizes sum to s-1
            for sizes in itertools.product(range(s), repeat=k):
                if sum(sizes) != s - 1:
                    continue
                pools = []
                ok = True
                for cs, ct in zip(sizes, blk.param_types):
                    lst = by_size[cs].get(ct, [])
                    if not lst:
                        ok = False
                        break
                    pools.append(lst)
                if not ok:
                    continue
                for children in itertools.product(*pools):
                    combos += 1
                    if combos > max_combos_per_prim_size:
                        truncated = True
                        break
                    out = []
                    for idx in range(len(tuples)):
                        cvals = [c[1][idx] for c in children]
                        if any(v == ERR for v in cvals):
                            out.append(ERR)
                            continue
                        # raw (uncanonical) child values are not kept; canonical
                        # forms are safe to feed back in for these impls except
                        # list[color] (tuple vs list) — convert back.
                        cvals = [list(v) if isinstance(v, tuple) else v for v in cvals]
                        try:
                            out.append(canonical(blk.fn(*cvals)))
                        except Exception:
                            out.append(ERR)
                    term = ("A", bname, tuple(c[0] for c in children))
                    add(s, blk.return_type, term, tuple(out))
                if combos > max_combos_per_prim_size:
                    break
    return EnumResult(seen=seen, tuples=tuples, truncated=truncated, n_terms=n_terms)


# ---------------------------------------------------------------------------
# Target matching + held-out verification
# ---------------------------------------------------------------------------


@dataclass
class Derivation:
    target: str
    size: int
    term: str
    support: tuple[str, ...]
    verified: bool


def target_vector(blk: Block, tuples: list[tuple[Any, ...]]) -> tuple[Any, ...]:
    out = []
    for t in tuples:
        try:
            out.append(canonical(blk.fn(*t)))
        except Exception:
            out.append(ERR)
    return tuple(out)


def target_valid_count(target: Block) -> int:
    """How many primary sample tuples the target itself succeeds on (cheap pre-check)."""
    tuples = sample_tuples(target.param_types, PRIMARY_POOLS, N_PRIMARY)
    return sum(1 for v in target_vector(target, tuples) if v != ERR)


def find_derivations(
    target: Block,
    result: EnumResult,
    blocks: dict[str, Block],
    *,
    min_valid: int = 6,
    max_witnesses: int = 3,
) -> tuple[list[Derivation], int] | None:
    """Minimal-size behavioral matches for ``target`` over the enumerated pool.

    Returns (derivations, n_valid_primary) or None if the target has too few
    valid primary tuples to be judged at all.
    """
    tvec = target_vector(target, result.tuples)
    valid = [i for i, v in enumerate(tvec) if v != ERR]
    if len(valid) < min_valid:
        return None
    bucket = result.seen.get(target.return_type, {})
    matches: list[tuple[int, tuple[Any, ...]]] = []
    for vec, (size, term) in bucket.items():
        if all(vec[i] == tvec[i] for i in valid):
            matches.append((size, term))
    if not matches:
        return [], len(valid)
    matches.sort(key=lambda x: (x[0], term_str(x[1])))
    min_size = matches[0][0]
    out: list[Derivation] = []
    holdout = sample_tuples(target.param_types, HOLDOUT_POOLS, N_HOLDOUT)
    hvec = target_vector(target, holdout)
    hvalid = [i for i, v in enumerate(hvec) if v != ERR]
    for size, term in matches:
        if size > min_size or len(out) >= max_witnesses:
            break
        ok = len(hvalid) >= 3
        for i in hvalid:
            w = eval_term(term, holdout[i], blocks)
            if w == ERR or canonical(w) != hvec[i]:
                ok = False
                break
        out.append(
            Derivation(
                target=target.name,
                size=size,
                term=term_str(term),
                support=tuple(sorted(term_support(term))),
                verified=ok,
            )
        )
    return out, len(valid)
