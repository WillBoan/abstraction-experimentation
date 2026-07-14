# New CLI commands (scratch notes)

## `arc-lab check-library-coherence` — check one bundle's coherence

Checks type-closure, goal-directedness, and hole-fill sufficiency for a single bundle.

```
uv run arc-lab check-library-coherence <LIBRARY>
uv run arc-lab check-library-coherence --primitives "read,build_grid,width,height,sub" --name my-floor
uv run arc-lab check-library-coherence FLOOR --constant-sources finite-enumerate --constant-sources harvest-from-instance
```

- `LIBRARY` resolves against three registries in order:
  1. `presets.py::LIBRARIES` (`d4`, `symmetry`, `atomic`, `build`, `build-affine`, `cells`, `hof`, `mask`)
  2. preset names (`sym`, `synth`, `beam`, via their `.library`)
  3. the bundle sheet (`FLOOR`, `MASK_BASIC`, etc. — see below)
- `--primitives` bypasses all registries — comma-separated primitive names, resolved live from the substrate registry. Zero code changes needed to try something new.
- `--constant-sources` (repeatable) controls which Int/Color/Bool leaf policy to assume; defaults to `finite-enumerate`.
- Output: COHERENT/INCOHERENT, reachable types, goal-directedness, dead primitives, and a findings list (`!` = error, `?` = warning).

## `arc-lab check-primitive-bundles` — batch-check every bundle in the candidate sheet

```
uv run arc-lab check-primitive-bundles       # one summary line per bundle
uv run arc-lab check-primitive-bundles -v    # + full findings per bundle
```

- Walks `execution/bundle_sheet.py::BUNDLES` (33 entries seeded from `_PRIMITIVE_BUNDLES2.md`'s Fragments + Floors tables) and prints coherent/incoherent + error/warning counts for each.
- To add a bundle you're considering: add one `BundleSpec(...)` entry to `BUNDLES` in that file — no other code changes, and it's immediately checkable by both commands (by name in `check-library-coherence`, or automatically in the batch run).
