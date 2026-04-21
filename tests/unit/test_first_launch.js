/**
 * Jest tests for electron/first_launch.js
 * Uses real fs in tmp directory.
 */

const fs = require('fs').promises;
const path = require('path');
const os = require('os');

let tmpDir;
let firstLaunchModule;

beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'forgesdlc-test-'));
    jest.resetModules();

    // Override home dir to tmpDir
    jest.spyOn(os, 'homedir').mockReturnValue(tmpDir);

    firstLaunchModule = require('../../electron/first_launch');
});

afterEach(async () => {
    jest.restoreAllMocks();
    await fs.rm(tmpDir, { recursive: true, force: true });
});

test('test_first_launch_writes_flag_file_after_run', async () => {
    const { runFirstLaunch, fileExists } = firstLaunchModule;
    const flagFile = path.join(tmpDir, '.forgesdlc', 'first_launch_done');

    expect(await fileExists(flagFile)).toBe(false);
    await runFirstLaunch();
    expect(await fileExists(flagFile)).toBe(true);
});

test('test_first_launch_skips_when_flag_file_exists', async () => {
    const { runFirstLaunch, mergeJsonFile } = firstLaunchModule;

    // Write flag file first
    const flagDir = path.join(tmpDir, '.forgesdlc');
    await fs.mkdir(flagDir, { recursive: true });
    await fs.writeFile(path.join(flagDir, 'first_launch_done'), 'done');

    // Create cursor dir to detect
    const cursorDir = path.join(tmpDir, '.cursor');
    await fs.mkdir(cursorDir, { recursive: true });
    const mcpPath = path.join(cursorDir, 'mcp.json');

    await runFirstLaunch();

    // mcp.json should NOT have been written (skipped)
    const { fileExists } = firstLaunchModule;
    expect(await fileExists(mcpPath)).toBe(false);
});

test('test_first_launch_writes_cursor_mcp_json_when_cursor_dir_exists', async () => {
    const { runFirstLaunch } = firstLaunchModule;

    // Create ~/.cursor directory
    const cursorDir = path.join(tmpDir, '.cursor');
    await fs.mkdir(cursorDir, { recursive: true });

    await runFirstLaunch();

    const mcpPath = path.join(cursorDir, 'mcp.json');
    const content = JSON.parse(await fs.readFile(mcpPath, 'utf8'));
    expect(content.mcpServers.forgesdlc).toBeDefined();
    expect(content.mcpServers.forgesdlc.url).toBe('http://localhost:8080/mcp');
});

test('test_first_launch_idempotent_no_duplicate_forgesdlc_entry', async () => {
    const { mergeJsonFile } = firstLaunchModule;

    const mcpPath = path.join(tmpDir, 'mcp.json');
    const entry = { mcpServers: { forgesdlc: { url: 'http://localhost:8080/mcp' } } };

    await mergeJsonFile(mcpPath, entry);
    await mergeJsonFile(mcpPath, entry);  // second write

    const content = JSON.parse(await fs.readFile(mcpPath, 'utf8'));
    const keys = Object.keys(content.mcpServers).filter(k => k === 'forgesdlc');
    expect(keys.length).toBe(1);
});

test('test_merge_json_file_preserves_existing_mcp_entries', async () => {
    const { mergeJsonFile } = firstLaunchModule;

    const mcpPath = path.join(tmpDir, 'mcp.json');

    // Write existing config with another server
    await fs.writeFile(mcpPath, JSON.stringify({
        mcpServers: { 'other-server': { url: 'http://other:9090/mcp' } }
    }));

    await mergeJsonFile(mcpPath, {
        mcpServers: { forgesdlc: { url: 'http://localhost:8080/mcp' } }
    });

    const content = JSON.parse(await fs.readFile(mcpPath, 'utf8'));
    expect(content.mcpServers['other-server']).toBeDefined();
    expect(content.mcpServers['forgesdlc']).toBeDefined();
});