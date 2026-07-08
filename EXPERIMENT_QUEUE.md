# Experiment queue

Planned experiments for arc-lab — a **drain-only queue**, rough priority order, top = next. This is _state, not events_ (the counterpart to `EXPERIMENTS.md`): it holds what we currently intend to run, and it only shrinks or gets deliberately re-fed.

**Discipline** (or this rots like its predecessor):

- **Drain on run.** When an experiment runs, its `EXPERIMENTS.md` entry is the record — delete the queue row in the same session. Rejected without running → delete too (log a dead-end entry first if the reason is itself a finding).
- **No IDs.** E-numbers are minted at run time, in the log — never here. (Pre-assigned numbers forked from the log's numbering once already.) Rows get names, not numbers.
- **Experiments only.** Machinery-level work is never queued here — `MACHINERY.md` tracks it (Status / Gates). The **Unmet machinery** column links each experiment to the not-yet-built mechanisms that gate it (by `MACHINERY.md` row name); when one ships, flip its Status there and clear it here.
- **One row's worth of sizing.** The columns _are_ the sizing frame; full design is still design-time work for the experiment about to run.

---

| Experiment | Starting primitives | Target abstraction(s) (as a template) | New primitives to build | Abstractor demands | Unmet machinery | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| **perceive→transform** | `map_color`, `most_common_color` | `recolor_bg(g,c) = map_color(g, most_common_color(g), c)` | `most_common_color` (1) | var-sharing (grid ×2) | none | "Derive the parameter." First _perceiver-consuming_ abstraction; real-ARC-useful. Runnable today. |
| **layered abstraction** | `flip_h`, `flip_v`, `map_color` | L1: `rot180 = flip_h(flip_v(g))`; L2: `recolor_flipped(g,a,b) = map_color(rot180(g),a,b)` | none | none (each param once) | none | **Multi-generation**: L2 built _on the learned L1_. Cleanest test of abstractions-on-abstractions. Runnable today. |
| **learned intermediate type** | `nonbg_mask`, `crop_to_mask` | `crop_to_content(g) = crop_to_mask(g, nonbg_mask(g))` | `nonbg_mask`, `crop_to_mask` (2) | var-sharing + abstraction over a new type | - `Mask` `ValueType` activation (F0, reserved)<br> - `Enumerate` Mask pool support | Abstraction that constructs _and_ consumes a learned intermediate type — the deepest phenomenon here. |
| **reusable-idiom governance** | affine cell floor + `build_grid` (the E8/E9 environment) | `mirror_index(n,k) = sub(sub(n,k),1)`, minted for _reusability_ — not by type-fiat | none | usefulness-scored selection (run search / held-out transfer per candidate), on the _naive_ proposer | - **search-aware / transfer-aware governance** (F4, 🔜)<br> - alt: invent-broad + prune-unused (F4, ⚪) | The general, open-ended fix to the **E8 compression/reusability divergence**: E8/E9 recovered `mirror_index` only by _scoping invention to what the search composes_ — a labelled **stopgap** that's anti-open-ended. Does letting _usefulness_ (not train-DL node-count) decide mint the reusable idiom over the larger `COLOR` read-bodies, with no type gag? The fully-general alternative — **library refactoring** (compress the library, extract the shared factor into a hierarchy) — is ≈ Stitch's core, deferred to real-ARC scale (MACHINERY F4). Successor to the drained **`mirror_index` bootstrap** (done: E8/E9). |
