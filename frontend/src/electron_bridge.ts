/**
 * electron_bridge.ts — Typed wrapper for window.electronAPI.
 *
 * Provides type-safe access to the contextBridge API exposed in preload.js.
 * Import this instead of casting (window as any).electronAPI everywhere.
 */

export interface McpStatus {
    status: "stopped" | "starting" | "running" | "error";
    port: number;
    pid: number | null;
}

export interface HitlResult {
    success?: boolean;
    error?: string;
}

export interface ElectronAPI {
    hitlApprove: (projectId: string) => Promise<HitlResult>;
    hitlCorrect: (projectId: string, correction: string) => Promise<HitlResult>;
    getMcpStatus: () => Promise<McpStatus>;
    onStatusChange: (callback: (data: McpStatus) => void) => () => void;
    onHitlReady: (callback: (data: { stage: string }) => void) => () => void;
    platform: "win32" | "darwin" | "linux";
}

// Type-safe accessor — throws if not running in Electron
export function getElectronAPI(): ElectronAPI {
    const api = (window as unknown as { electronAPI?: ElectronAPI }).electronAPI;
    if (!api) {
        throw new Error(
            "window.electronAPI not found. " +
            "Ensure contextBridge is set up in preload.js and " +
            "contextIsolation: true in BrowserWindow webPreferences."
        );
    }
    return api;
}

// Safe accessor — returns null outside Electron (e.g. browser dev mode)
export function getElectronAPISafe(): ElectronAPI | null {
    return (window as unknown as { electronAPI?: ElectronAPI }).electronAPI ?? null;
}