"""``arc-lab lsp``: run the `.ladder` language server on stdio (for an editor client).

The VS Code extension launches this. pygls is an optional dependency (the ``lsp`` extra), imported
lazily so the rest of the CLI works without it. **stdout is the JSON-RPC channel** -- logging is
forced to stderr before the server starts, and this command prints nothing itself.
"""

from __future__ import annotations

import logging
import sys


def lsp_command() -> None:
    """Start the `.ladder` language server, serving an editor over stdin/stdout."""
    try:
        from arc_lab.program_search.ladders.lsp.server import create_server
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without the extra
        import typer

        raise typer.BadParameter(
            "the `.ladder` language server needs the `lsp` extra: run `uv sync --extra lsp`"
        ) from exc

    # Keep stdout clean for JSON-RPC; every log line goes to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    create_server().start_io()
