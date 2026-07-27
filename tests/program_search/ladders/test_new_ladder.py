"""``arc-lab new-ladder``: the guarded write.

Five ladder variants were destroyed through a single filename on 2026-07-25, two unrecoverably. A
git-tracked-only guard would not have caught it (none had been committed), so the guard is at the
write and the supported way to make the next variant is a copy under a new name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from arc_lab.cli import new_ladder
from arc_lab.program_search.ladders.lang.parse import parse_ladder_file


def _write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(new_ladder, "DRAFTS_ROOT", tmp_path)
    return tmp_path


def test_it_refuses_to_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write(tmp_path, monkeypatch)
    new_ladder.new_ladder_command("v1", source=None, registry=False, force=False)
    original = (root / "v1.ladder").read_text(encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="already exists"):
        new_ladder.new_ladder_command("v1", source=None, registry=False, force=False)

    assert (root / "v1.ladder").read_text(encoding="utf-8") == original  # untouched


def test_force_is_the_deliberate_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write(tmp_path, monkeypatch)
    new_ladder.new_ladder_command("v1", source=None, registry=False, force=False)
    (root / "v1.ladder").write_text("ladder v1\n# edited\n", encoding="utf-8")

    new_ladder.new_ladder_command("v1", source=None, registry=False, force=True)
    assert "# edited" not in (root / "v1.ladder").read_text(encoding="utf-8")


def test_a_variant_copies_and_renames_leaving_the_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: making variant N+1 must be cheaper than reusing a name.

    The `ladder <name>` header is rewritten to match the filename -- otherwise the copy would load
    as its parent and silently shadow it.
    """
    root = _write(tmp_path, monkeypatch)
    new_ladder.new_ladder_command(
        "al21-copy", source="al21-dag-siblings", registry=False, force=False
    )

    copied = root / "al21-copy.ladder"
    assert parse_ladder_file(copied).name == "al21-copy"
    # The source is a registry ladder and must be untouched by the copy.
    assert "al21-dag-siblings" in copied.read_text(encoding="utf-8")  # its prose survives
    from arc_lab.program_search.ladders.registry import ladder_paths

    assert parse_ladder_file(ladder_paths()["al21-dag-siblings"]).name == "al21-dag-siblings"


def test_a_fresh_draft_parses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The scaffold must be a syntactically valid `.ladder`, or the first thing a new ladder does
    is fail to load for a reason that has nothing to do with its design."""
    root = _write(tmp_path, monkeypatch)
    new_ladder.new_ladder_command("scaffold", source=None, registry=False, force=False)
    document = parse_ladder_file(root / "scaffold.ladder")
    assert document.name == "scaffold"
    assert document.floor_name == "scaffold-L0"


def test_an_unknown_source_names_what_is_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, monkeypatch)
    with pytest.raises(typer.BadParameter, match="registered:"):
        new_ladder.new_ladder_command("v", source="no-such-ladder", registry=False, force=False)
