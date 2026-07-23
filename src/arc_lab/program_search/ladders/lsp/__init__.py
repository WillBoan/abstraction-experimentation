"""The `.ladder` language server package.

``server``/``convert`` require the ``lsp`` extra (pygls + lsprotocol); ``shim`` does not, so the
diagnostic production is importable and testable on its own. Nothing here is imported eagerly by the
rest of the package -- the CLI reaches it lazily via ``arc-lab lsp``.
"""

from __future__ import annotations
