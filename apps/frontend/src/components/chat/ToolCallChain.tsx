import { useState } from 'react'
import type { ToolCallView, ToolCallStatus } from '../../lib/groupEvents'

const TOOL_ICONS: Record<string, string> = {
  'screen.perceive': '📸',
  'screen.click': '🖱️',
  'screen.type': '⌨️',
  'screen.key': '⌨️',
  'screen.scroll': '⤡',
}

const STATUS_STYLE: Record<ToolCallStatus, string> = {
  requested: 'border-purple-500/30 text-purple-300',
  validated: 'border-purple-500/30 text-purple-300',
  success: 'border-green-500/30 text-green-300',
  failed: 'border-red-500/30 text-red-300',
  denied: 'border-red-500/30 text-red-300',
}

const STATUS_ICON: Record<ToolCallStatus, string> = {
  requested: '⋯',
  validated: '⋯',
  success: '✓',
  failed: '✗',
  denied: '✗',
}

/** Short inline hint (file path, command, url…) so the chain reads as progress. */
function argHint(call: ToolCallView): string | undefined {
  const a = call.args
  if (!a) return undefined
  // Screen tool-specific hints
  if (call.tool === 'screen.click') {
    if (a.element_id != null) return `elem ${a.element_id}`
    if (a.x != null && a.y != null) return `(${a.x}, ${a.y})`
    return undefined
  }
  if (call.tool === 'screen.type') {
    const t = (a.text as string | undefined) ?? ''
    return t.length > 44 ? t.slice(0, 42) + '…' : t || undefined
  }
  if (call.tool === 'screen.key') return (a.combo as string | undefined) ?? undefined
  if (call.tool === 'screen.scroll') {
    const dx = a.dx as number | undefined
    const dy = a.dy as number | undefined
    if (dx != null || dy != null) return `dx=${dx ?? 0} dy=${dy ?? 0}`
    return undefined
  }
  const raw = (a.path ?? a.source_path ?? a.url ?? a.command ?? a.target_agent_id) as
    | string
    | undefined
  if (!raw) return undefined
  const s = String(raw)
  return s.length > 44 ? '…' + s.slice(-42) : s
}

export function ToolCallCard({ call }: { call: ToolCallView }) {
  const [open, setOpen] = useState(false)
  const style = STATUS_STYLE[call.status]
  const hasDetail = !!call.args || !!call.resultPreview || !!call.error
  const hint = argHint(call)

  return (
    <div className={`rounded-md border bg-slate-900/60 px-2.5 py-1.5 text-xs ${style}`}>
      <button
        className="flex items-center justify-between w-full gap-2"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        disabled={!hasDetail}
      >
        <span className="flex items-center gap-2 min-w-0">
          <span>{TOOL_ICONS[call.tool] ?? '🔧'}</span>
          <span className="font-mono shrink-0">{call.tool}</span>
          {hint && <span className="font-mono text-slate-500 truncate">{hint}</span>}
          <span aria-label={call.status} className="shrink-0">{STATUS_ICON[call.status]}</span>
        </span>
        {hasDetail && <span className="text-slate-500 shrink-0">{open ? '▲' : '▼'}</span>}
      </button>
      {open && hasDetail && (
        <div className="mt-2 space-y-2">
          {call.args && (
            <div>
              <p className="text-slate-500 mb-0.5">Arguments</p>
              <pre className="bg-slate-950 rounded p-2 overflow-x-auto whitespace-pre-wrap text-slate-300">
                {JSON.stringify(call.args, null, 2)}
              </pre>
            </div>
          )}
          {call.resultPreview && (
            <div>
              <p className="text-slate-500 mb-0.5">Result</p>
              <pre className="bg-slate-950 rounded p-2 overflow-x-auto whitespace-pre-wrap text-slate-300">
                {call.resultPreview}
              </pre>
            </div>
          )}
          {call.error && <p className="text-red-300">{call.error}</p>}
        </div>
      )}
    </div>
  )
}

/** Renders the ordered chain of tool calls a turn made, inline in the chat flow. */
export function ToolCallChain({ toolCalls }: { toolCalls: ToolCallView[] }) {
  if (toolCalls.length === 0) return null
  return (
    <div className="mt-2 space-y-1.5">
      {toolCalls.map(call => (
        <ToolCallCard key={call.key} call={call} />
      ))}
    </div>
  )
}
