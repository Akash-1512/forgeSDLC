import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

// MCP entry — workspace-level config, not global
const MCP_SERVER_KEY = 'forgesdlc';
const MCP_ENTRY: Record<string, unknown> = {
    [MCP_SERVER_KEY]: {
        url: 'http://localhost:8080/mcp'
    }
};

/**
 * Extension activation point.
 * Works in VS Code, Cursor, and Windsurf — same extension engine.
 */
export function activate(context: vscode.ExtensionContext): void {
    // On startup: check if already configured, offer if not
    checkAndNotify();

    // Command: add forgeSDLC to .vscode/mcp.json (idempotent)
    const addToMCP = vscode.commands.registerCommand('forgesdlc.addToMCP', () => {
        const success = writeMCPConfig();
        if (success) {
            vscode.window.showInformationMessage(
                'forgeSDLC added to MCP config. Start the server: npx @forgesdlc/agent'
            );
        }
    });

    // Command: open companion panel (iframe to local MCP server UI)
    const openPanel = vscode.commands.registerCommand('forgesdlc.openPanel', () => {
        const panel = vscode.window.createWebviewPanel(
            'forgesdlc',
            'forgeSDLC',
            vscode.ViewColumn.Beside,
            { enableScripts: true }
        );
        panel.webview.html = getWebviewContent();
    });

    context.subscriptions.push(addToMCP, openPanel);
}

/**
 * Check if .vscode/mcp.json already has the forgeSDLC entry.
 * If not, offer to add it via notification.
 */
function checkAndNotify(): void {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceRoot) return;

    const mcpPath = path.join(workspaceRoot, '.vscode', 'mcp.json');

    if (fs.existsSync(mcpPath)) {
        try {
            const existing = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
            if (existing?.mcpServers?.[MCP_SERVER_KEY]) {
                return; // Already configured — no notification needed
            }
        } catch {
            // Malformed JSON — will be handled by writeMCPConfig merge
        }
    }

    // Offer to add
    vscode.window.showInformationMessage(
        'forgeSDLC detected. Add to MCP config?',
        'Add to MCP',
        'Dismiss'
    ).then(selection => {
        if (selection === 'Add to MCP') {
            writeMCPConfig();
        }
    });
}

/**
 * Write forgeSDLC MCP entry to .vscode/mcp.json.
 * Writes to workspace-level .vscode/mcp.json — NOT ~/.cursor/mcp.json.
 * Idempotent: merges with existing config, overwrites forgesdlc key only.
 *
 * @returns true on success, false if no workspace folder open
 */
export function writeMCPConfig(): boolean {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceRoot) {
        vscode.window.showErrorMessage('forgeSDLC: No workspace folder open');
        return false;
    }

    // Workspace-level: .vscode/mcp.json (NOT ~/.cursor/mcp.json — global is wrong)
    const vscodeDir = path.join(workspaceRoot, '.vscode');
    const mcpPath = path.join(vscodeDir, 'mcp.json');

    // Ensure .vscode/ directory exists
    if (!fs.existsSync(vscodeDir)) {
        fs.mkdirSync(vscodeDir, { recursive: true });
    }

    // Idempotent merge — read existing config first
    let existing: Record<string, unknown> = {};
    if (fs.existsSync(mcpPath)) {
        try {
            existing = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
        } catch {
            // Start fresh if file is malformed
            existing = {};
        }
    }

    // Merge: spread existing, overwrite mcpServers.forgesdlc (idempotent)
    const merged = {
        ...existing,
        mcpServers: {
            ...((existing.mcpServers as Record<string, unknown>) || {}),
            ...MCP_ENTRY,  // overwrites existing forgesdlc entry — idempotent
        }
    };

    fs.writeFileSync(mcpPath, JSON.stringify(merged, null, 2));
    return true;
}

function getWebviewContent(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>forgeSDLC</title></head>
<body style="margin:0;padding:0;background:#0d1117;">
<iframe
  src="http://localhost:8080"
  width="100%"
  height="100%"
  style="border:none;min-height:100vh;"
  title="forgeSDLC companion panel">
</iframe>
</body>
</html>`;
}

export function deactivate(): void {
    // No cleanup needed
}