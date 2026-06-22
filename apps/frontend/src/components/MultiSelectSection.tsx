import { useMemo, useState, type ReactNode } from 'react'

export interface SelectableItem {
  id: string
  name: string
  /** Monospace secondary line (usually the id). */
  mono?: string
  /** Small muted meta line (description, tool list…). */
  meta?: ReactNode
  /** Renders the name in amber + a "critical" tag. */
  critical?: boolean
  /** Right-aligned status pill (e.g. enabled/disabled). */
  status?: { text: string; ok: boolean }
  /** Extra haystack text for search. */
  search?: string
}

interface Props {
  title: string
  icon: string
  hint?: string
  items: SelectableItem[]
  selected: string[]
  onChange: (ids: string[]) => void
  emptyText: string
  searchPlaceholder?: string
  /** Show selected items as chips below the list. */
  showChips?: boolean
}

/**
 * A grant list with bulk actions (Select all / Clear), live search, a
 * selected/total counter, and accessible rows. Powers the Capabilities, Skills,
 * Plugins and MCP sections of the agent form so they look and behave alike.
 */
export function MultiSelectSection({
  title, icon, hint, items, selected, onChange, emptyText, searchPlaceholder, showChips,
}: Props) {
  const [query, setQuery] = useState('')
  const selectedSet = useMemo(() => new Set(selected), [selected])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter(it =>
      it.name.toLowerCase().includes(q) ||
      (it.mono ?? '').toLowerCase().includes(q) ||
      (it.search ?? '').toLowerCase().includes(q),
    )
  }, [items, query])

  const allIds = useMemo(() => items.map(i => i.id), [items])
  const allSelected = items.length > 0 && allIds.every(id => selectedSet.has(id))

  const toggle = (id: string) => {
    onChange(selectedSet.has(id) ? selected.filter(x => x !== id) : [...selected, id])
  }
  const selectAll = () => onChange(Array.from(new Set([...selected, ...allIds])))
  const clearAll = () => onChange(selected.filter(id => !allIds.includes(id)))

  const selectedCount = allIds.filter(id => selectedSet.has(id)).length
  const showSearch = items.length > 6

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-slate-800 bg-slate-900/80 px-4 py-3">
        <span className="text-base leading-none" aria-hidden>{icon}</span>
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
        {items.length > 0 && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium tabular-nums ${
              selectedCount > 0 ? 'bg-blue-500/15 text-blue-300' : 'bg-slate-800 text-slate-400'
            }`}
          >
            {selectedCount}/{items.length}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={selectAll}
            disabled={items.length === 0 || allSelected}
            className="rounded-md px-2 py-1 text-xs font-medium text-blue-300 hover:bg-blue-500/10 disabled:opacity-40 disabled:hover:bg-transparent"
          >
            Select all
          </button>
          <button
            type="button"
            onClick={clearAll}
            disabled={selectedCount === 0}
            className="rounded-md px-2 py-1 text-xs font-medium text-slate-400 hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent"
          >
            Clear
          </button>
        </div>
      </header>

      <div className="p-4 space-y-3">
        {hint && <p className="text-xs leading-relaxed text-slate-500">{hint}</p>}

        {items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-800 px-3 py-6 text-center text-sm text-slate-500">
            {emptyText}
          </p>
        ) : (
          <>
            {showSearch && (
              <input
                type="search"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder={searchPlaceholder ?? `Search ${title.toLowerCase()}…`}
                className="form-input h-9 text-xs"
              />
            )}

            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {filtered.map(item => {
                const checked = selectedSet.has(item.id)
                return (
                  <label
                    key={item.id}
                    className={`group flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2 transition-colors ${
                      checked
                        ? 'border-blue-500/40 bg-blue-500/10'
                        : 'border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-800/50'
                    }`}
                  >
                    <input
                      aria-label={item.name}
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(item.id)}
                      className="mt-0.5 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500/50"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className={`truncate text-sm font-medium ${item.critical ? 'text-amber-300' : 'text-slate-200'}`}>
                          {item.name}
                        </span>
                        {item.critical && (
                          <span className="shrink-0 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-400/90">
                            critical
                          </span>
                        )}
                        {item.status && (
                          <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                            item.status.ok ? 'bg-green-500/15 text-green-300' : 'bg-slate-700 text-slate-400'
                          }`}>
                            {item.status.text}
                          </span>
                        )}
                      </span>
                      {item.mono && (
                        <span className="mt-0.5 block truncate font-mono text-[11px] text-slate-500">{item.mono}</span>
                      )}
                      {item.meta && (
                        <span className="mt-0.5 block truncate text-[11px] text-slate-500">{item.meta}</span>
                      )}
                    </span>
                  </label>
                )
              })}
            </div>

            {filtered.length === 0 && (
              <p className="py-2 text-center text-xs text-slate-500">No matches for “{query}”.</p>
            )}

            {showChips && selectedCount > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {items.filter(i => selectedSet.has(i.id)).map(i => (
                  <span key={i.id} className="rounded bg-blue-500/15 px-2 py-0.5 text-xs text-blue-300">
                    {i.name}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
