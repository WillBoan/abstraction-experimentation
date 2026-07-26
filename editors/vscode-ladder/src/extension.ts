import {
  ExtensionContext,
  RelativePattern,
  Uri,
  commands,
  window,
  workspace,
} from "vscode";
import {
  Executable,
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;

/** Coalesce a burst of file events (a formatter, a `git checkout`) into ONE restart. */
const RESTART_DEBOUNCE_MS = 750;

export function activate(context: ExtensionContext): void {
  const config = workspace.getConfiguration("ladder");
  const command = config.get<string>("server.command", "uv");
  const args = config.get<string[]>("server.args", ["run", "arc-lab", "lsp"]);
  const configuredCwd = config.get<string>("server.cwd", "");
  const cwd = configuredCwd || workspace.workspaceFolders?.[0]?.uri.fsPath;

  // One `arc-lab lsp` process over stdio. The same executable serves both run and debug.
  const executable: Executable = { command, args, options: { cwd } };
  const serverOptions: ServerOptions = { run: executable, debug: executable };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "ladder" }],
  };

  client = new LanguageClient(
    "ladder-ls",
    "Ladder Language Server",
    serverOptions,
    clientOptions,
  );

  client.start().catch((err: unknown) => {
    window.showErrorMessage(`Ladder language server failed to start: ${String(err)}`);
  });

  context.subscriptions.push(
    commands.registerCommand("ladder.restartServer", () => restart("command")),
  );
  registerSourceWatchers(context, config, cwd);
}

/**
 * Restart the server process.
 *
 * The server builds `BASE_PRIMITIVES` (and the whole check plan) at IMPORT time, so a long-lived
 * process lints against the substrate as it stood when the process launched. Adding a primitive
 * mid-session makes the floor of every open `.ladder` file report it as unresolved until the
 * process is replaced -- that staleness is the whole reason this exists.
 */
async function restart(trigger: "command" | "watch"): Promise<void> {
  if (client === undefined) {
    return;
  }
  try {
    await client.restart();
    if (trigger === "command") {
      window.setStatusBarMessage("Ladder language server restarted", 3000);
    }
  } catch (err: unknown) {
    window.showErrorMessage(`Ladder language server failed to restart: ${String(err)}`);
  }
}

/**
 * Watch the Python sources the diagnostics are computed FROM, and restart when they change.
 *
 * Deliberately not the whole package: only the substrate (which decides whether a floor's
 * primitives resolve) and the ladders package (parser + check plan). Editing a search engine
 * cannot change what a `.ladder` file lints to, so it should not cost a process restart.
 */
function registerSourceWatchers(
  context: ExtensionContext,
  config: ReturnType<typeof workspace.getConfiguration>,
  cwd: string | undefined,
): void {
  if (!config.get<boolean>("server.restartOnSourceChange", true) || cwd === undefined) {
    return;
  }
  const globs = config.get<string[]>("server.watchGlobs", []);
  let pending: NodeJS.Timeout | undefined;
  const schedule = (): void => {
    if (pending !== undefined) {
      clearTimeout(pending);
    }
    pending = setTimeout(() => {
      pending = undefined;
      void restart("watch");
    }, RESTART_DEBOUNCE_MS);
  };

  const base = Uri.file(cwd);
  for (const glob of globs) {
    const watcher = workspace.createFileSystemWatcher(new RelativePattern(base, glob));
    watcher.onDidChange(schedule, undefined, context.subscriptions);
    watcher.onDidCreate(schedule, undefined, context.subscriptions);
    watcher.onDidDelete(schedule, undefined, context.subscriptions);
    context.subscriptions.push(watcher);
  }
  context.subscriptions.push({
    dispose: () => {
      if (pending !== undefined) {
        clearTimeout(pending);
      }
    },
  });
}

export function deactivate(): Thenable<void> | undefined {
  return client?.stop();
}
