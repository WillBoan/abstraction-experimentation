"""Shared corpus resolution for the CLI commands.

A corpus name is a dataset name (``arc1-train``), a testbed name (``e1-rot90``), or a
testbed split (``e1-rot90:train`` / ``e1-rot90:heldout``).
"""

from __future__ import annotations

import typer

from arc_lab.core.dataset import ARC_DATASETS, Corpus, load_dataset, load_testbed
from arc_lab.program_search.execution.studies import split_by_meta


def load_corpus(name: str) -> Corpus:
    """Resolve a corpus name (see module docstring); raises ``typer.BadParameter``."""
    base, _, split = name.partition(":")
    try:
        corpus = load_dataset(base) if base in ARC_DATASETS else load_testbed(base)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not split:
        return corpus
    if split not in ("train", "heldout"):
        raise typer.BadParameter(f"unknown split {split!r} (use ':train' or ':heldout')")
    train, heldout = split_by_meta(corpus)
    return train if split == "train" else heldout
