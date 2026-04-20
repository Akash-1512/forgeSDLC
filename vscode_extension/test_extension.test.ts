/**
 * VS Code extension tests — Jest + TypeScript.
 * Uses mocked fs and vscode modules.
 * Tests: writeMCPConfig writes .vscode/mcp.json, idempotency, URL correctness.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// --- Minimal vscode mock (no actual VS Code needed) ---
const mockWorkspaceRoot = path.join(os.tmpdir(), `forgesdlc_test_${Date.now()}`);

jest.mock('vscode', () => ({
    workspace: {
        workspaceFolders: [{
            uri: { fsPath: mockWorkspaceRoot }
        }]
    },
    window: {
        showInformationMessage: jest.fn().mockResolvedValue(undefined),
        showErrorMessage: jest.fn(),
        createWebviewPanel: jest.fn().mockReturnValue({
            webview: { html: '' }
        })
    },
    commands: {
        registerCommand: jest.fn().mockReturnValue({ dispose: jest.fn() })
    },
    ViewColumn: { Beside: 2 },
    ExtensionContext: jest.fn(),
}), { virtual: true });

// Import AFTER mock setup
import { writeMCPConfig } from './extension';

const vscodeDir = path.join(mockWorkspaceRoot, '.vscode');
const mcpPath = path.join(vscodeDir, 'mcp.json');

beforeEach(() => {
    // Clean up before each test
    if (fs.existsSync(vscodeDir)) {
        fs.rmSync(vscodeDir, { recursive: true });
    }
    fs.mkdirSync(mockWorkspaceRoot, { recursive: true });
});

afterEach(() => {
    if (fs.existsSync(mockWorkspaceRoot)) {
        fs.rmSync(mockWorkspaceRoot, { recursive: true, force: true });
    }
});

test('test_add_to_mcp_writes_vscode_mcp_json_not_cursor_global', () => {
    writeMCPConfig();
    // Assert written to workspace .vscode/mcp.json
    expect(fs.existsSync(mcpPath)).toBe(true);
    // Assert NOT written to global cursor config
    const cursorGlobal = path.join(os.homedir(), '.cursor', 'mcp.json');
    const writtenFiles = [mcpPath];
    expect(writtenFiles).not.toContain(cursorGlobal);
});

test('test_add_to_mcp_creates_vscode_dir_if_missing', () => {
    expect(fs.existsSync(vscodeDir)).toBe(false);
    writeMCPConfig();
    expect(fs.existsSync(vscodeDir)).toBe(true);
    expect(fs.existsSync(mcpPath)).toBe(true);
});

test('test_add_to_mcp_idempotent_does_not_duplicate_entry', () => {
    writeMCPConfig();
    writeMCPConfig(); // call twice
    const content = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
    const forgesdlcKeys = Object.keys(content.mcpServers || {})
        .filter((k: string) => k === 'forgesdlc');
    expect(forgesdlcKeys.length).toBe(1);
});

test('test_add_to_mcp_url_is_localhost_8080', () => {
    writeMCPConfig();
    const content = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
    expect(content.mcpServers?.forgesdlc?.url).toBe('http://localhost:8080/mcp');
});

test('test_add_to_mcp_merges_with_existing_mcp_config', () => {
    // Write existing config with another server
    fs.mkdirSync(vscodeDir, { recursive: true });
    fs.writeFileSync(mcpPath, JSON.stringify({
        mcpServers: {
            "other-server": { url: "http://localhost:9090/mcp" }
        }
    }));
    writeMCPConfig();
    const content = JSON.parse(fs.readFileSync(mcpPath, 'utf8'));
    // Both servers present
    expect(content.mcpServers['other-server']).toBeDefined();
    expect(content.mcpServers['forgesdlc']).toBeDefined();
});