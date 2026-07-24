import { ExtensionContext, workspace, window } from "vscode";
import {
  Executable,
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;

export function activate(_context: ExtensionContext): void {
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
}

export function deactivate(): Thenable<void> | undefined {
  return client?.stop();
}
