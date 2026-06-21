import { useState } from 'react'

/**
 * Collapsible "chain of thought" block. Shows model reasoning (when available)
 * and is hidden by default to keep the chat flow clean.
 */
export function ThinkingBlock({ thinking }: { thinking: string }) {
  const [open, setOpen] = useState(false)
  if (!thinking.trim()) return null

  return (
    <div className="mt-2 border-l-2 border-slate-600 pl-3">
      <button
        className="text-xs text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
      >
        <span>{open ? '▾' : '▸'}</span>
        <span>Thinking</span>
      </button>
      {open && (
        <pre className="mt-1 text-xs text-slate-400 whitespace-pre-wrap font-sans">{thinking}</pre>
      )}
    </div>
  )
}
