'use strict'

const { contextBridge, ipcRenderer } = require('electron')

// Retrieve API base URL synchronously from main process before any page script runs.
// This guarantees window.electronAPI.apiBaseUrl is ready when client.ts is evaluated.
const apiBaseUrl = ipcRenderer.sendSync('get-api-url')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  version: process.versions.electron,
  apiBaseUrl,
})
