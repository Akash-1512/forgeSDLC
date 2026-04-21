/**
 * updater.js — Auto-update via electron-updater + GitHub Releases.
 *
 * Non-blocking: checkForUpdates() errors are swallowed in main.js.
 * The app MUST start even if the update check fails (no network, etc).
 * Actual publish to GitHub Releases happens in Session 20 with GH_TOKEN.
 */

let autoUpdater;

// Lazy-require electron-updater — may not be installed in dev
try {
    autoUpdater = require('electron-updater').autoUpdater;
} catch {
    autoUpdater = null;
}

/**
 * Check for updates from GitHub Releases.
 * Non-blocking — caller does: checkForUpdates().catch(() => {})
 * Never crashes the app — all errors swallowed or re-thrown for caller to catch.
 */
async function checkForUpdates() {
    if (!autoUpdater) {
        // electron-updater not available (dev environment) — skip silently
        return;
    }

    // Suppress update dialogs — handle manually
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = false;

    autoUpdater.on('update-available', (info) => {
        console.log(`[Updater] Update available: ${info.version}`);
        // In Session 20: notify renderer via IPC to show update banner
    });

    autoUpdater.on('error', (err) => {
        // Swallow — update failure must never crash the app
        console.warn('[Updater] Update check failed:', err.message);
    });

    await autoUpdater.checkForUpdates();
}

module.exports = { checkForUpdates };