/**
 * server_manager.js — Manages the Python MCP server child process.
 *
 * Lifecycle:
 *   stopped → starting → running → (crash) → stopped → (auto-restart after 2s)
 *   stopped → starting → running → (stop()) → stopped  [no auto-restart]
 *
 * Windows safety: PYTHON_PATH env var takes priority over "python".
 * "python" on Windows may resolve to Windows Store stub, not venv Python.
 */

const { spawn } = require('child_process');
const path = require('path');

class ServerManager {
    constructor() {
        this.process = null;
        this.port = 8080;
        this.status = 'stopped';  // 'stopped' | 'starting' | 'running' | 'error'
        this._intentionalStop = false;
    }

    async start() {
        this._intentionalStop = false;
        this.status = 'starting';

        // PYTHON_PATH env var → "python" fallback (Windows venv safety)
        const python = process.env.PYTHON_PATH || 'python';

        // Server module path — relative to electron/ directory
        const serverArgs = [
            '-m', 'mcp_server.server',
            '--transport', 'streamable-http',
            '--port', String(this.port),
        ];

        this.process = spawn(python, serverArgs, {
            env: { ...process.env },
            stdio: ['ignore', 'pipe', 'pipe'],
            // cwd: project root (one level up from electron/)
            cwd: path.join(__dirname, '..'),
        });

        this.process.stdout.on('data', (data) => {
            const msg = data.toString();
            if (msg.includes('Running on') || msg.includes('Uvicorn running')) {
                this.status = 'running';
            }
        });

        this.process.stderr.on('data', (data) => {
            // Log stderr but don't change status — uvicorn writes to stderr normally
            console.error('[MCP Server]', data.toString().trim());
        });

        this.process.on('exit', (code) => {
            this.status = 'stopped';
            this.process = null;

            // Auto-restart on crash — NOT on intentional stop (code === null)
            // code === null: process killed via signal (stop() → SIGTERM)
            // code !== 0:    process crashed
            if (!this._intentionalStop && code !== 0 && code !== null) {
                console.log(`[ServerManager] Server exited with code ${code}. Restarting in 2s...`);
                setTimeout(() => this.start(), 2000);
            }
        });

        // Poll health until running or timeout
        await this._waitForHealth(10_000);
    }

    async _waitForHealth(timeoutMs) {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            try {
                // fetch is available in Node 18+ (Electron 32 uses Node 22)
                const r = await fetch(`http://localhost:${this.port}/health`);
                if (r.ok) {
                    this.status = 'running';
                    return;
                }
            } catch {
                // Server not ready yet — keep polling
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        this.status = 'error';
        throw new Error(`MCP server did not start within ${timeoutMs / 1000}s`);
    }

    getStatus() {
        return {
            status: this.status,
            port: this.port,
            pid: this.process ? this.process.pid : null,
        };
    }

    async sendApproval(projectId) {
        const r = await fetch(`http://localhost:${this.port}/hitl/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: projectId,
                confirmation: '100% GO',  // internal constant — never in UI text
            }),
        });
        return r.json();
    }

    async sendCorrection(projectId, correction) {
        const r = await fetch(`http://localhost:${this.port}/hitl/correct`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: projectId,
                correction,
                // Server overwrites state["human_corrections"][-1], does not append
            }),
        });
        return r.json();
    }

    stop() {
        this._intentionalStop = true;
        if (this.process) {
            this.process.kill('SIGTERM');
            // process.on('exit') fires with code=null → auto-restart suppressed
        }
        this.status = 'stopped';
    }
}

module.exports = { ServerManager };