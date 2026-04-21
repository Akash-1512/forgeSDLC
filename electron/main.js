/**
 * main.js — Electron main process.
 *
 * Security: contextIsolation: true, nodeIntegration: false — non-negotiable.
 * All IPC through preload.js contextBridge only.
 * Minimises to tray on close — does not quit.
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const { setupTray } = require('./tray');
const { ServerManager } = require('./server_manager');
const { checkForUpdates } = require('./updater');
const { runFirstLaunch } = require('./first_launch');
const path = require('path');

let mainWindow = null;
let tray = null;
const server = new ServerManager();

app.whenReady().then(async () => {
    // 1. Start MCP server before anything else
    try {
        await server.start();
    } catch (err) {
        console.error('[Main] MCP server failed to start:', err.message);
        // Continue — show window anyway so user can see error state
    }

    // 2. First-launch wizard (idempotent — skips if already done)
    try {
        await runFirstLaunch();
    } catch (err) {
        console.warn('[Main] First-launch wizard failed:', err.message);
    }

    // 3. Create companion panel window
    mainWindow = new BrowserWindow({
        width: 420,
        height: 800,
        minWidth: 380,
        minHeight: 600,
        titleBarStyle: 'hiddenInset',
        title: 'forgeSDLC',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,   // REQUIRED — security boundary
            nodeIntegration: false,   // REQUIRED — no Node in renderer
            sandbox: true,
        },
    });

    if (process.env.NODE_ENV === 'development') {
        mainWindow.loadURL('http://localhost:3000');
        mainWindow.webContents.openDevTools({ mode: 'detach' });
    } else {
        mainWindow.loadFile(
            path.join(__dirname, '../frontend/build/index.html')
        );
    }

    // 4. System tray — minimise to tray on close
    tray = setupTray(mainWindow);

    mainWindow.on('close', (e) => {
        e.preventDefault();  // Intercept close — hide instead of quit
        mainWindow.hide();
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // 5. Check for updates (non-blocking — errors swallowed)
    checkForUpdates().catch(() => {});

    // Push MCP status changes to renderer
    server._statusChangeCallback = (status) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('mcp:status-change', { status });
        }
    };
});

// Keep app running even when all windows closed (tray mode)
app.on('window-all-closed', (e) => {
    if (e) e.preventDefault();
    // Do NOT call app.quit() — stay alive in tray
});

app.on('before-quit', () => {
    // Graceful shutdown: SIGTERM MCP server before exiting
    server.stop();
});

// ── IPC Handlers ──────────────────────────────────────────────────────────────

// Renderer asks for current MCP server status
ipcMain.handle('mcp:status', () => {
    return server.getStatus();
});

// Renderer: [✅ Approve] button pressed
// Sends "100% GO" to MCP server — "100% GO" NEVER appears in UI text
ipcMain.handle('hitl:approve', async (_, { projectId }) => {
    try {
        return await server.sendApproval(projectId);
    } catch (err) {
        return { error: err.message };
    }
});

// Renderer: correction submitted
// Server overwrites state["human_corrections"][-1] — never appends
ipcMain.handle('hitl:correct', async (_, { projectId, correction }) => {
    try {
        return await server.sendCorrection(projectId, correction);
    } catch (err) {
        return { error: err.message };
    }
});

// Main process notifies tray when agent reaches HITL gate
// Called from MCP server webhook or polling in future sessions
ipcMain.handle('hitl:notify', (_, { stage }) => {
    if (tray && tray.notifyHitl) {
        tray.notifyHitl(stage);
    }
});