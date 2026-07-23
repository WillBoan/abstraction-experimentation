"""The `.ladder` language server (pygls) -- Phase A vertical slice.

On open / change / save it runs the strict pipeline (via :func:`shim.diagnose`) and publishes
line-level diagnostics; on close it clears them. This is the thin pygls binding: all diagnostic
production is in :mod:`shim` (pygls-free, unit-tested), all wire conversion in :mod:`convert`.

Runtime contract: **stdout carries only JSON-RPC** -- the ``arc-lab lsp`` entry point forces logging
to stderr before starting the server. Later phases add debouncing, a cheap/full tier split, semantic
tokens, and navigation; the shim's per-keystroke full lint is fine at this scale (see the baseline
test) and is replaced, not merely tuned, when the shared pipeline lands.
"""

from __future__ import annotations

import logging

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from .convert import to_lsp
from .shim import diagnose

logger = logging.getLogger(__name__)

SERVER_NAME = "ladder-ls"
SERVER_VERSION = "0.1.0"


def create_server() -> LanguageServer:
    """Build the language server with its document-sync handlers registered."""
    server = LanguageServer(SERVER_NAME, SERVER_VERSION)

    # pygls 2.x calls a feature handler with a single `params` arg; the server is reached via closure.
    # Tier policy (see shim): change runs the ~2ms parse+resolve tier; open/save run the full lint
    # (seconds on a deep ladder). A sync handler blocks the loop during a full lint -- acceptable for
    # the shim on the rare open/save; Phase H moves the full tier to a thread with debounce.
    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def _did_open(params: lsp.DidOpenTextDocumentParams) -> None:
        _publish(server, params.text_document.uri, run_lint=True)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def _did_change(params: lsp.DidChangeTextDocumentParams) -> None:
        _publish(server, params.text_document.uri, run_lint=False)

    @server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
    def _did_save(params: lsp.DidSaveTextDocumentParams) -> None:
        _publish(server, params.text_document.uri, run_lint=True)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
    def _did_close(params: lsp.DidCloseTextDocumentParams) -> None:
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
        )

    return server


def _publish(server: LanguageServer, uri: str, *, run_lint: bool) -> None:
    """Re-analyse the document at ``uri`` and publish its diagnostics (version-stamped)."""
    document = server.workspace.get_text_document(uri)
    diagnostics = [to_lsp(d, uri=uri) for d in diagnose(document.source, run_lint=run_lint)]
    server.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, version=document.version, diagnostics=diagnostics)
    )
