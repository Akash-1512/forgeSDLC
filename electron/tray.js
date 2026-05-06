/**
 * tray.js — System tray icon and approval gate notifications.
 *
 * Tray icon shows/hides the companion panel on click.
 * notifyApprovalGate(stage): pulses icon + shows notification when agent reaches approval gate.
 * Icon resets to default after 3s.
 */

const { Tray, Menu, nativeImage, Notification, app } = require('electron');
const path = require('path');

function setupTray(mainWindow) {
    const iconPath = path.join(__dirname, '../frontend/public/tray-icon.png');
    const activeIconPath = path.join(__dirname, '../frontend/public/tray-icon-active.png');

    // Graceful fallback — if icon file missing, use empty image (won't crash)
    let icon;
    try {
        icon = nativeImage.createFromPath(iconPath);
        if (icon.isEmpty()) {
            icon = nativeImage.createEmpty();
        }
    } catch {
        icon = nativeImage.createEmpty();
    }

    const tray = new Tray(icon);
    tray.setToolTip('forgeSDLC — SDLC Intelligence Layer');

    // Context menu
    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Open forgeSDLC',
            click: () => {
                mainWindow.show();
                mainWindow.focus();
            },
        },
        { type: 'separator' },
        {
            label: 'MCP Server Status',
            enabled: false,  // display only — updated dynamically in main.js
            id: 'status-item',
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                mainWindow.destroy();
                app.exit(0);
            },
        },
    ]);
    tray.setContextMenu(contextMenu);

    // Click tray icon → toggle window visibility
    tray.on('click', () => {
        if (mainWindow.isVisible() && mainWindow.isFocused()) {
            mainWindow.hide();
        } else {
            mainWindow.show();
            mainWindow.focus();
        }
    });

    /**
     * notifyApprovalGate(stage) — called by main process when an agent reaches an approval gate.
     * Pulses the tray icon and shows a system notification.
     * Icon resets to default after 3s.
     *
     * @param {string} stage — e.g. "architecture_review", "deployment"
     */
    tray.notifyHitl = (stage) => {
        // Pulse: switch to active icon
        try {
            const activeIcon = nativeImage.createFromPath(activeIconPath);
            if (!activeIcon.isEmpty()) {
                tray.setImage(activeIcon);
            }
        } catch {
            // Active icon missing — skip pulse, still show notification
        }

        // System notification
        if (Notification.isSupported()) {
            const notif = new Notification({
                title: 'forgeSDLC — Review Required',
                body: `${stage} is ready for your approval. Click to open.`,
                icon: icon.isEmpty() ? undefined : icon,
                silent: false,
            });
            notif.on('click', () => {
                mainWindow.show();
                mainWindow.focus();
            });
            notif.show();
        }

        // Reset icon after 3s
        setTimeout(() => {
            try {
                tray.setImage(icon);
            } catch {
                // Window may have been destroyed — ignore
            }
        }, 3000);
    };

    return tray;
}

module.exports = { setupTray };