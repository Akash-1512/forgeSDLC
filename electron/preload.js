/**
 * preload.js — Electron security boundary.
 *
 * contextIsolation: true means React components cannot call require().
 * ALL Node/Electron APIs must go through this contextBridge.
 * window.electronAPI is the ONLY interface between renderer and main process.
 *
 * Do NOT expose:
 * - require (would break contextIsolation)
 * - ipcRenderer directly (exposes all channels)
 * - shell, fs, path (renderer should never touch filesystem directly)
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    /**
     * HITL gate: send "100% GO" programmatically.
     * "100% GO" is the internal constant — NEVER shown in UI text.
     * UI shows [✅ Approve]. Server receives "100% GO".
     */
    hitlApprove: (projectId) =>
        ipcRenderer.invoke('hitl:approve', { projectId }),

    /**
     * HITL correction: overwrites state["human_corrections"][-1] on server.
     * displayed_interpretation is replaced — user sees only current interpretation.
     */
    hitlCorrect: (projectId, correction) =>
        ipcRenderer.invoke('hitl:correct', { projectId, correction }),

    /**
     * MCP server health status.
     * Returns: { status: 'stopped'|'starting'|'running'|'error', port: number }
     */
    getMcpStatus: () => ipcRenderer.invoke('mcp:status'),

    /**
     * Subscribe to MCP server status changes pushed from main process.
     * Returns cleanup function — call it to unsubscribe.
     */
    onStatusChange: (callback) => {
        const handler = (_, data) => callback(data);
        ipcRenderer.on('mcp:status-change', handler);
        return () => ipcRenderer.removeListener('mcp:status-change', handler);
    },

    /**
     * Subscribe to HITL gate notifications (stage ready for approval).
     * Returns cleanup function.
     */
    onHitlReady: (callback) => {
        const handler = (_, data) => callback(data);
        ipcRenderer.on('hitl:ready', handler);
        return () => ipcRenderer.removeListener('hitl:ready', handler);
    },

    /**
     * Platform info — read-only, safe to expose.
     * 'win32' | 'darwin' | 'linux'
     */
    platform: process.platform,
});