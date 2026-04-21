/**
 * first_launch.js — One-time setup wizard.
 *
 * Runs ONCE on first app launch (flag file: ~/.forgesdlc/first_launch_done).
 * Detects installed editors and writes global MCP configs.
 *
 * Cursor: ~/.cursor/mcp.json  ← GLOBAL (all projects)
 *   Different from VS Code extension which writes .vscode/mcp.json (per-project workspace).
 *   Desktop app is a system-level tool → global config is correct here.
 *
 * Idempotent: mergeJsonFile reads existing JSON before writing.
 *             forgesdlc key is overwritten (not duplicated) on repeat runs.
 */

const fs = require('fs').promises;
const path = require('path');
const os = require('os');

const FLAG_FILE = path.join(os.homedir(), '.forgesdlc', 'first_launch_done');

const MCP_ENTRY = {
    forgesdlc: {
        url: 'http://localhost:8080/mcp',
    },
};

/**
 * Run first-launch wizard. Idempotent — skips silently if flag file exists.
 */
async function runFirstLaunch() {
    if (await fileExists(FLAG_FILE)) {
        return;  // Already completed — skip
    }

    await detectAndConfigureEditors();

    // Write flag file to prevent re-running
    await fs.mkdir(path.dirname(FLAG_FILE), { recursive: true });
    await fs.writeFile(FLAG_FILE, new Date().toISOString(), 'utf8');
}

/**
 * Detect installed editors and write MCP configs.
 * Currently supports: Cursor (global ~/.cursor/mcp.json).
 * Future: Claude Desktop, Windsurf global config.
 */
async function detectAndConfigureEditors() {
    const cursorConfigDir = path.join(os.homedir(), '.cursor');
    if (await fileExists(cursorConfigDir)) {
        const mcpPath = path.join(cursorConfigDir, 'mcp.json');
        await mergeJsonFile(mcpPath, { mcpServers: MCP_ENTRY });
    }
}

/**
 * Idempotent JSON merge — reads existing file, merges mcpServers, writes back.
 * Object spread means duplicate forgesdlc key is overwritten, never appended.
 *
 * @param {string} filepath
 * @param {{ mcpServers: Record<string, unknown> }} newData
 */
async function mergeJsonFile(filepath, newData) {
    let existing = {};
    if (await fileExists(filepath)) {
        try {
            const raw = await fs.readFile(filepath, 'utf8');
            existing = JSON.parse(raw);
        } catch {
            // Malformed JSON — start fresh
            existing = {};
        }
    }

    const merged = {
        ...existing,
        mcpServers: {
            ...(existing.mcpServers || {}),
            ...newData.mcpServers,  // overwrites forgesdlc key — idempotent
        },
    };

    const dir = path.dirname(filepath);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(filepath, JSON.stringify(merged, null, 2), 'utf8');
}

/**
 * Safe file/directory existence check.
 */
async function fileExists(p) {
    try {
        await fs.access(p);
        return true;
    } catch {
        return false;
    }
}

module.exports = { runFirstLaunch, mergeJsonFile, fileExists };