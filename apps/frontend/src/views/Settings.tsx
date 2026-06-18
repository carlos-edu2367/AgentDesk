import { useEffect, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { storageApi } from '../api/storage'
import type { StorageInfo } from '../types/domain'

export function Settings() {
  const [storage, setStorage] = useState<StorageInfo | null>(null)

  useEffect(() => {
    storageApi.info().then(setStorage).catch(() => {})
  }, [])

  return (
    <div>
      <TopBar title="Settings" description="Application configuration" />

      <div className="space-y-4 max-w-xl">
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Storage</h2>
          {storage ? (
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-slate-500">AppData path</dt>
                <dd className="text-slate-200 font-mono text-xs mt-0.5">{storage.appdata_path}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Database path</dt>
                <dd className="text-slate-200 font-mono text-xs mt-0.5">{storage.database_path}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-slate-500 text-sm">Loading storage info...</p>
          )}
        </div>

        <div className="card opacity-60">
          <h2 className="text-sm font-semibold text-slate-300 mb-2">Coming in future phases</h2>
          <ul className="text-sm text-slate-500 space-y-1 list-disc list-inside">
            <li>Memory configuration</li>
            <li>Teams management</li>
            <li>MCP Servers</li>
            <li>Skills &amp; Plugins</li>
            <li>Audit Logs</li>
            <li>Approval settings</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
