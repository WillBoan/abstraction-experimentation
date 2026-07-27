"""``arc-lab new-ladder``: start a `.ladder` file, or a VARIANT of one, without clobbering.

The guarded write. Ladder variants are the unit of ladder design -- most of the work is "try this
decomposition, then that one" -- and on 2026-07-25 five of them went through a single filename and
were destroyed, two unrecoverably. A git-tracked-only guard would not have caught it: none of the
five was ever committed.

So the machinery is a writer that **refuses to overwrite**, and a ``--from`` that makes "the next
variant" cheaper than reusing a name. ``--force`` stays for the typo case, where clobbering is what
you actually mean.

This is deliberately the only thing in the repo that writes a `.ladder`: ``taskgen`` reads one to
build a testbed, and everything else (lint, probe, run) is read-only. A scratch script can of
course still write one itself -- nothing can stop that -- but there is now a supported path that
cannot lose work, and `LADDER-PROCESS-2026-07-26.md` names it as the one to use.
"""

from __future__ import annotations

from pathlib import Path

import typer

from arc_lab.program_search.ladders.lang.parse import LADDER_SUFFIX
from arc_lab.program_search.ladders.registry import LADDER_ROOT, ladder_paths

DRAFTS_ROOT = LADDER_ROOT.parent / "drafts"

#: A minimal ladder that PARSES AND LOADS as written -- a placeholder spine over two real
#: primitives, with two demonstrations and a top. Deliberately not a comment skeleton: a scaffold
#: that fails to parse means the first thing a new ladder does is fail for a reason that has
#: nothing to do with its design. Replace every part of it; it is a starting shape, not a default.
_TEMPLATE = """ladder {name}

# {name}: <the anchor competence, in one line>
#
# <Why this decomposition: what each rung is a nameable competence FOR, and what the top needs that
# the floor cannot reach. Record dead ends here too -- a retired variant's file persists as the
# finding (LADDERS.md). Design guidance: docs/abstraction_ladders/LADDER-PROCESS-2026-07-26.md>
#
# PLACEHOLDER SPINE -- replace the floor, the rung and the tasks. It loads as written so that
# `lint-ladder` gives you a real reading from the first edit.

config {{
    budget.depth_limit: 2
}}

floor {name}-L0 {{
    use flip_h: (Grid) -> Grid
    use flip_v: (Grid) -> Grid
}}

rung {{
    rung1(g: Grid) -> Grid = flip_h(flip_v(g))

    task rung1-00 {{
        solution: rung1(input)
        train [[1, 2], [3, 4]]
        train [[5, 6], [7, 8]]
        test  [[2, 4], [6, 8]]
    }}
    task rung1-01 {{
        solution: rung1(input)
        train [[2, 3], [4, 5]]
        train [[6, 7], [8, 9]]
        test  [[3, 5], [7, 9]]
    }}
}}

top {{
    task {name}-top {{
        solution: flip_h(rung1(input))
        train [[1, 2], [3, 4]]
        train [[5, 6], [7, 8]]
        test  [[2, 4], [6, 8]]
    }}
}}
"""


def new_ladder_command(
    name: str = typer.Argument(..., help="The new ladder's name (its filename stem)."),
    source: str | None = typer.Option(
        None,
        "--from",
        help="Start from an existing ladder (a registered name, or a path). This is how to make "
        "the NEXT VARIANT of a decomposition: copy, rename, edit -- so the previous variant "
        "survives as a file rather than being overwritten.",
    ),
    registry: bool = typer.Option(
        False,
        "--registry",
        help="Write into ladders/registry/ (a batch member) instead of ladders/drafts/. A "
        "registry ladder is scanned by taskgen/run-ladder and needs a LADDERS.md row.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite an existing file. Destroys whatever is there."
    ),
) -> None:
    """Create a new `.ladder` file (a draft by default), refusing to overwrite an existing one."""
    root = LADDER_ROOT if registry else DRAFTS_ROOT
    target = root / f"{name}{LADDER_SUFFIX}"

    if target.exists() and not force:
        raise typer.BadParameter(
            f"{target} already exists. A ladder file is the record of a decomposition that was "
            f"tried -- overwriting one loses it, including the variants that were rejected (which "
            f"are the findings). Pick a new name (e.g. `{name}-2`), or pass --force to clobber."
        )

    if source is None:
        body = _TEMPLATE.format(name=name)
    else:
        body = _read_source(source)
        # The `ladder <name>` header is the file's identity and must follow the filename, or the
        # copy would load as its parent and quietly shadow it.
        body = _rename_header(body, name)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    where = "registry" if registry else "drafts"
    typer.echo(f"wrote {target} ({where})")
    if source is not None:
        typer.echo(f"  copied from {source}; the original is untouched")
    typer.echo(f"  next: uv run arc-lab lint-ladder {target}" + ("" if registry else " --draft"))


def _read_source(source: str) -> str:
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8")
    known = ladder_paths()
    if source in known:
        return known[source].read_text(encoding="utf-8")
    draft = DRAFTS_ROOT / f"{source}{LADDER_SUFFIX}"
    if draft.exists():
        return draft.read_text(encoding="utf-8")
    raise typer.BadParameter(
        f"--from {source!r} is neither a path, a registered ladder, nor a draft; "
        f"registered: {', '.join(sorted(known))}"
    )


def _rename_header(body: str, name: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("ladder "):
            lines[index] = f"ladder {name}"
            return "\n".join(lines) + "\n"
    return f"ladder {name}\n\n" + body
