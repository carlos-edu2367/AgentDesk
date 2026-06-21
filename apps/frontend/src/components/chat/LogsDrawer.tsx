import { useState } from 'react'
import type { ExecutionEvent } from '../../types/domain'

function LogRow({ event }: { event: ExecutionEvent }) {
  const [open, setOpen] = useState(false)
  const hasContent = Object.keys(event.content ?? {}).length > 0
  return (
    <div className="border-b border-slate-800 py-1.5 text-xs">
      <button
        className="flex items-center justify-between w-full gap-2 text-left"
        onClick={() => setOpen(v => !v)}
        disabled={!hasContent}
      >
        <span className="flex items-center gap-2 min-w-0">
          <span className="text-slate-500 shrink-0">
            {new Date(event.created_at).toLocaleTimeString()}
          </span>
          <span className="font-mono text-slate-300 truncate">{event.type}</span>
        </span>
        {hasContent && <span className="text-slate-600 shrink-0">{open ? '▲' : '▼'}</span>}
      </button>
      {open && hasContent && (
        <pre className="mt-1 text-slate-400 overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(event.content, null, 2)}
        </pre>
      )}
    </div>
  )
}

/**
 * Collapsible side drawer holding the raw event timeline for the active turn.
 * Kept out of the chat flow; opened on demand for debugging (design decision A).
 */
export function LogsDrawer({
  events,
  open,
  onToggle,
}: {
  events: ExecutionEvent[]
  open: boolean
  onToggle: () => void
}) {
  if (!open) {
    return (
      <button
        className="btn-ghost text-xs shrink-0"
        onClick={onToggle}
        aria-label="Open logs"
      >
        Logs ▸
      </button>
    )
  }

  return (
    <aside className="w-[300px] shrink-0 border-l border-slate-800 bg-slate-950/60 flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800">
        <span className="text-xs font-semibold text-slate-300">Logs (raw timeline)</span>
        <button className="text-slate-500 hover:text-slate-300 text-xs" onClick={onToggle} aria-label="Close logs">
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-1">
        {events.length === 0 ? (
          <p className="text-xs text-slate-500 py-4">No events for this turn.</p>
        ) : (
          events.map(ev => <LogRow key={ev.id} event={ev} />)
        )}
      </div>
    </aside>
  )
}
