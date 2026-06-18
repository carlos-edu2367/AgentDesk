// Preload script runs in the renderer context with Node access (before page load).
// Keep this minimal. All communication with main process should go through contextBridge.
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  version: process.versions.electron,
})
