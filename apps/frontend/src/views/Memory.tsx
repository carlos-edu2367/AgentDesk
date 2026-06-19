import { useCallback, useEffect, useMemo, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { memoriesApi } from '../api/memories'
import type {
  Memory as MemoryRecord,
  MemoryCreate,
  MemoryScope,
  MemorySearchResult,
  MemoryType,
} from '../types/domain'

const SCOPES: MemoryScope[] = ['global', 'agent', 'team', 'workspace']
const TYPES: MemoryType[] = [
  'profile',
  'preference',
  'project',
  'file_reference',
  'task_history',
  'decision',
  'lesson',
  'error_pattern',
  'workflow',
  'system_note',
]

const EMBEDDING_BADGE: Record<string, string> = {
  done: 'bg-green-500/20 text-green-300',
  failed: 'bg-red-500/20 text-red-300',
  pending: 'bg-amber-500/20 text-amber-300',
}

const initialForm: Partial<MemoryCreate> = {
  scope: 'global',
  type: 'preference',
  title: '',
  content: '',
  tags: [],
  confidence: 0.8,
  importance: 0.7,
  source: {},
}

export function Memory() {
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterScope, setFilterScope] = useState('')
  const [filterType, setFilterType] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode] = useState<'text' | 'semantic' | 'hybrid'>('hybrid')
  const [searchResults, setSearchResults] = useState<MemorySearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [form, setForm] = useState<Partial<MemoryCreate>>(initialForm)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: { scope?: string; type?: string } = {}
      if (filterScope) params.scope = filterScope
      if (filterType) params.type = filterType
      setMemories(await memoriesApi.list(params))
    } catch {
      setError('Failed to load memories')
    } finally {
      setLoading(false)
    }
  }, [filterScope, filterType])

  useEffect(() => {
    load()
  }, [load])

  const searchResultById = useMemo(() => {
    return new Map((searchResults ?? []).map(result => [result.memory_id, result]))
  }, [searchResults])

  const displayList = useMemo(() => {
    if (searchResults === null) return memories

    return searchResults.map(result => ({
      id: result.memory_id,
      scope: result.scope as MemoryScope,
      scope_id: result.scope_id,
      type: result.type as MemoryType,
      title: result.title,
      content: result.content,
      tags: result.tags,
      confidence: result.confidence,
      importance: result.importance,
      source: {},
      created_at: '',
      updated_at: '',
      last_used_at: null,
      usage_count: 0,
      deleted_at: null,
      embedding_status: result.has_embedding ? 'done' : 'pending',
    } satisfies MemoryRecord))
  }, [memories, searchResults])

  const handleSearch = async () => {
    const query = searchQuery.trim()
    if (!query) return

    setSearching(true)
    try {
      const response = await memoriesApi.search({
        query,
        scopes: filterScope ? [filterScope] : ['global'],
        mode: searchMode,
        limit: 20,
      })
      setSearchResults(response.results)
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleCreate = async () => {
    if (!form.title?.trim() || !form.content?.trim()) return

    try {
      await memoriesApi.create(form as MemoryCreate)
      setShowForm(false)
      setForm(initialForm)
      setSearchResults(null)
      await load()
    } catch {
      setError('Failed to create memory')
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this memory?')) return

    try {
      await memoriesApi.delete(id)
      setSearchResults(null)
      await load()
    } catch {
      setError('Failed to delete memory')
    }
  }

  if (loading) return <LoadingState message="Loading memories..." />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Memory"
        description={`${memories.length} memories`}
        actions={
          <button className="btn-primary" onClick={() => setShowForm(true)}>
            New Memory
          </button>
        }
      />

      <div className="space-y-4">
        <div className="card">
          <div className="flex flex-wrap items-end gap-2">
            <select
              value={filterScope}
              onChange={event => {
                setFilterScope(event.target.value)
                setSearchResults(null)
              }}
              className="form-select w-auto min-w-32"
            >
              <option value="">All scopes</option>
              {SCOPES.map(scope => (
                <option key={scope} value={scope}>{scope}</option>
              ))}
            </select>

            <select
              value={filterType}
              onChange={event => {
                setFilterType(event.target.value)
                setSearchResults(null)
              }}
              className="form-select w-auto min-w-40"
            >
              <option value="">All types</option>
              {TYPES.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>

            <input
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') handleSearch()
              }}
              placeholder="Search memories..."
              className="form-input min-w-56 flex-1"
            />

            <select
              value={searchMode}
              onChange={event => setSearchMode(event.target.value as 'text' | 'semantic' | 'hybrid')}
              className="form-select w-auto"
            >
              <option value="hybrid">Hybrid</option>
              <option value="text">Text</option>
              <option value="semantic">Semantic</option>
            </select>

            <button className="btn-secondary" onClick={handleSearch} disabled={searching}>
              {searching ? 'Searching...' : 'Search'}
            </button>

            {searchResults !== null && (
              <button className="btn-ghost" onClick={() => setSearchResults(null)}>
                Clear
              </button>
            )}
          </div>
        </div>

        {showForm && (
          <div className="card space-y-3">
            <h2 className="text-sm font-semibold text-slate-200">New Memory</h2>
            <div className="grid gap-3 md:grid-cols-2">
              <input
                placeholder="Title"
                value={form.title ?? ''}
                onChange={event => setForm(current => ({ ...current, title: event.target.value }))}
                className="form-input md:col-span-2"
              />
              <textarea
                placeholder="Content"
                value={form.content ?? ''}
                onChange={event => setForm(current => ({ ...current, content: event.target.value }))}
                rows={3}
                className="form-textarea md:col-span-2"
              />
              <select
                value={form.scope ?? 'global'}
                onChange={event => setForm(current => ({ ...current, scope: event.target.value as MemoryScope }))}
                className="form-select"
              >
                {SCOPES.map(scope => (
                  <option key={scope} value={scope}>{scope}</option>
                ))}
              </select>
              <select
                value={form.type ?? 'preference'}
                onChange={event => setForm(current => ({ ...current, type: event.target.value as MemoryType }))}
                className="form-select"
              >
                {TYPES.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
              <input
                placeholder="scope_id for agent, team, or workspace"
                value={form.scope_id ?? ''}
                onChange={event => setForm(current => ({ ...current, scope_id: event.target.value || null }))}
                className="form-input"
              />
              <input
                placeholder="tags, comma-separated"
                value={(form.tags ?? []).join(', ')}
                onChange={event => setForm(current => ({
                  ...current,
                  tags: event.target.value.split(',').map(tag => tag.trim()).filter(Boolean),
                }))}
                className="form-input"
              />
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Confidence: {form.confidence}
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={form.confidence ?? 0.8}
                  onChange={event => setForm(current => ({ ...current, confidence: Number(event.target.value) }))}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Importance: {form.importance}
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={form.importance ?? 0.7}
                  onChange={event => setForm(current => ({ ...current, importance: Number(event.target.value) }))}
                />
              </label>
            </div>
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleCreate}>
                Save
              </button>
            </div>
          </div>
        )}

        {searchResults !== null && (
          <p className="text-xs text-slate-500">
            Search results: {searchResults.length} found (mode: {searchMode})
          </p>
        )}

        <div className="space-y-2">
          {displayList.length === 0 && (
            <div className="card py-12 text-center text-sm text-slate-500">
              No memories found.
            </div>
          )}

          {displayList.map(memory => (
            <MemoryCard
              key={memory.id}
              memory={memory}
              searchResult={searchResultById.get(memory.id)}
              onDelete={() => handleDelete(memory.id)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function MemoryCard({
  memory,
  searchResult,
  onDelete,
}: {
  memory: MemoryRecord
  searchResult?: MemorySearchResult
  onDelete: () => void
}) {
  const embeddingClass = EMBEDDING_BADGE[memory.embedding_status] ?? 'bg-slate-700 text-slate-300'

  return (
    <div className="card hover:border-slate-700 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100">{memory.title}</h2>
            <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-xs text-blue-300">
              {memory.scope}
            </span>
            <span className="rounded bg-purple-500/20 px-1.5 py-0.5 text-xs text-purple-300">
              {memory.type}
            </span>
            {memory.scope_id && <span className="text-xs text-slate-500">{memory.scope_id}</span>}
            <span className={`rounded px-1.5 py-0.5 text-xs ${embeddingClass}`}>
              {memory.embedding_status === 'done' ? 'embedded' : memory.embedding_status}
            </span>
            {searchResult && (
              <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-xs text-amber-300">
                score {searchResult.score.toFixed(2)}
              </span>
            )}
          </div>

          <p className="line-clamp-2 text-sm text-slate-400">{memory.content}</p>

          {memory.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {memory.tags.map(tag => (
                <span key={tag} className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">
                  #{tag}
                </span>
              ))}
            </div>
          )}

          <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
            <span>confidence {memory.confidence.toFixed(1)}</span>
            <span>importance {memory.importance.toFixed(1)}</span>
            <span>used {memory.usage_count}x</span>
            {typeof memory.source.type === 'string' && <span>source: {memory.source.type}</span>}
          </div>
        </div>

        <button
          className="shrink-0 rounded px-2 py-1 text-xs text-red-400 hover:bg-red-500/10 hover:text-red-300"
          onClick={onDelete}
        >
          Delete
        </button>
      </div>
    </div>
  )
}
