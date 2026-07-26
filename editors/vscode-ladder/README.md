# vscode-ladder

Editor support for arc-lab `.ladder` files: TextMate syntax highlighting plus live diagnostics from the `arc-lab lsp` language server.

**Internal extension.** It assumes a working `uv` and an arc-lab checkout as the workspace; it is not built for the VS Code Marketplace. The default server command is `uv run arc-lab lsp`, launched from the first workspace folder.

This is the Phase A vertical slice of the editor-tooling plan (`docs/abstraction_ladders/AL-PLAN-LADDER-EDITOR-TOOLING-2026-07-23.md`): highlighting + line-level diagnostics over the current strict parser. Precise ranges, symbols, hover, and formatting arrive in later phases.

## Develop

```sh
cd editors/vscode-ladder
npm install
npm run compile          # bundle to dist/extension.js (npm run watch to rebuild on change)
```

Then press **F5** in VS Code (with this folder open) to launch an Extension Development Host, and open any `.ladder` file. You should see highlighting immediately and diagnostics once the server starts.

The language server needs the `lsp` extra installed in the arc-lab venv:

```sh
uv sync --extra lsp
```

## Staleness: why the server restarts itself

The server is **one long-lived process**, and it builds `BASE_PRIMITIVES` and the check plan at _import_ time. So it lints against the substrate as it stood when the process launched. Add a primitive mid-session and every open `.ladder` file that uses it reports `unknown primitive ..., not in the substrate registry` -- while `arc-lab lint-ladder`, which starts a fresh interpreter per invocation, says OK. The file is fine; the process is old.

Two things close that gap:

- **`Ladder: Restart Language Server`** in the command palette -- the manual out.
- A watcher on `ladder.server.watchGlobs` (the substrate and the ladders package -- the sources the diagnostics are actually computed _from_) that restarts automatically, debounced so a formatter or a `git checkout` costs one restart rather than fifty. Disable with `ladder.server.restartOnSourceChange`.

## Configuration

- `ladder.server.command` (default `uv`) and `ladder.server.args` (default `["run","arc-lab","lsp"]`) -- how the server is launched.
- `ladder.server.cwd` -- working directory (defaults to the first workspace folder).
- `ladder.server.restartOnSourceChange` (default `true`) and `ladder.server.watchGlobs` -- see above.
- `ladder.trace.server` -- `off` | `messages` | `verbose` LSP trace, shown in the "Ladder Language Server" output channel.

## Package

```sh
npm run package          # produces vscode-ladder-<version>.vsix (needs @vscode/vsce)
code --install-extension vscode-ladder-*.vsix
```
