import { useEffect, useMemo, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { skillsApi } from '../api/skills'
import type { Skill, SkillCreate } from '../types/domain'

const EMPTY_FORM: SkillCreate = {
  id: '',
  name: '',
  version: '0.1.0',
  description: '',
  tags: [],
  prompt: '',
  examples: [],
}

export function Skills() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<SkillCreate>(EMPTY_FORM)
  const [examplesText, setExamplesText] = useState('[]')
  const [importText, setImportText] = useState('')
  const [overwriteImport, setOverwriteImport] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setSkills(await skillsApi.list())
    } catch {
      setError('Failed to load skills')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filteredSkills = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return skills
    return skills.filter(skill =>
      skill.name.toLowerCase().includes(needle)
      || skill.description.toLowerCase().includes(needle)
      || skill.tags.some(tag => tag.toLowerCase().includes(needle))
      || skill.id.toLowerCase().includes(needle),
    )
  }, [query, skills])

  const startCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setExamplesText('[]')
    setShowForm(true)
  }

  const startEdit = (skill: Skill) => {
    setEditingId(skill.id)
    setForm({
      id: skill.id,
      name: skill.name,
      version: skill.version,
      description: skill.description,
      tags: skill.tags,
      prompt: skill.prompt,
      examples: skill.examples,
    })
    setExamplesText(JSON.stringify(skill.examples ?? [], null, 2))
    setShowForm(true)
  }

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      let examples: Record<string, unknown>[] = []
      try {
        examples = JSON.parse(examplesText || '[]')
      } catch {
        throw new Error('Examples must be valid JSON array')
      }
      const payload = { ...form, examples }
      if (editingId) {
        await skillsApi.update(editingId, {
          name: payload.name,
          version: payload.version,
          description: payload.description,
          tags: payload.tags,
          prompt: payload.prompt,
          examples,
        })
      } else {
        await skillsApi.create(payload)
      }
      setShowForm(false)
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (skill: Skill) => {
    if (!window.confirm(`Delete skill "${skill.name}"?`)) return
    await skillsApi.delete(skill.id)
    await load()
  }

  const handleImport = async () => {
    if (!importText.trim()) return
    try {
      const parsed = JSON.parse(importText)
      await skillsApi.importSkill(parsed, overwriteImport)
      setImportText('')
      await load()
    } catch (e) {
      setError(String(e))
    }
  }

  const handleExport = async (skill: Skill) => {
    const exported = await skillsApi.exportSkill(skill.id)
    setImportText(JSON.stringify(exported, null, 2))
  }

  if (loading) return <LoadingState message="Loading skills..." />
  if (error && skills.length === 0) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <TopBar
        title="Skills"
        description={`${skills.length} prompt-based skills`}
        actions={<button className="btn-primary" onClick={startCreate}>New Skill</button>}
      />

      <div className="space-y-4">
        {error && (
          <div className="rounded-md border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="card">
          <p className="mb-3 text-sm text-slate-300">
            Skills alteram o comportamento do agente, mas não executam código.
          </p>
          <input
            className="form-input"
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search by name, tag, description, or ID..."
          />
        </div>

        {showForm && (
          <form onSubmit={handleSave} className="card space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="form-label" htmlFor="skill-name">Name</label>
                <input id="skill-name" className="form-input" value={form.name} onChange={event => setForm(current => ({ ...current, name: event.target.value }))} required />
              </div>
              <div>
                <label className="form-label" htmlFor="skill-id">ID</label>
                <input id="skill-id" className="form-input font-mono" value={form.id} onChange={event => setForm(current => ({ ...current, id: event.target.value }))} disabled={Boolean(editingId)} required />
              </div>
              <div>
                <label className="form-label" htmlFor="skill-version">Version</label>
                <input id="skill-version" className="form-input" value={form.version} onChange={event => setForm(current => ({ ...current, version: event.target.value }))} required />
              </div>
              <div>
                <label className="form-label" htmlFor="skill-tags">Tags</label>
                <input
                  id="skill-tags"
                  className="form-input"
                  value={(form.tags ?? []).join(', ')}
                  onChange={event => setForm(current => ({
                    ...current,
                    tags: event.target.value.split(',').map(tag => tag.trim()).filter(Boolean),
                  }))}
                />
              </div>
              <div className="md:col-span-2">
                <label className="form-label" htmlFor="skill-description">Description</label>
                <input id="skill-description" className="form-input" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} required />
              </div>
              <div className="md:col-span-2">
                <label className="form-label" htmlFor="skill-prompt">Prompt</label>
                <textarea id="skill-prompt" className="form-textarea min-h-[180px]" value={form.prompt} onChange={event => setForm(current => ({ ...current, prompt: event.target.value }))} required />
              </div>
              <div className="md:col-span-2">
                <label className="form-label" htmlFor="skill-examples">Examples</label>
                <textarea id="skill-examples" className="form-textarea min-h-[90px] font-mono text-xs" value={examplesText} onChange={event => setExamplesText(event.target.value)} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setShowForm(false)}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? 'Saving...' : editingId ? 'Save Skill' : 'Create Skill'}
              </button>
            </div>
          </form>
        )}

        <div className="card space-y-3">
          <p className="text-sm font-semibold text-slate-200">Import / Export JSON</p>
          <textarea
            className="form-textarea min-h-[110px] font-mono text-xs"
            value={importText}
            onChange={event => setImportText(event.target.value)}
            placeholder='{"id":"skill_report_writer","name":"...","version":"0.1.0","description":"...","prompt":"..."}'
          />
          <div className="flex items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={overwriteImport} onChange={event => setOverwriteImport(event.target.checked)} />
              <span>Overwrite existing skill</span>
            </label>
            <button className="btn-secondary" onClick={handleImport} disabled={!importText.trim()}>
              Import JSON
            </button>
          </div>
        </div>

        {filteredSkills.length === 0 ? (
          <EmptyState
            title="No skills found"
            description="Create or import a prompt-based skill to specialize agents and teams."
            action={<button className="btn-primary" onClick={startCreate}>Create Skill</button>}
          />
        ) : (
          <div className="space-y-2">
            {filteredSkills.map(skill => (
              <SkillCard
                key={skill.id}
                skill={skill}
                onEdit={() => startEdit(skill)}
                onDelete={() => handleDelete(skill)}
                onExport={() => handleExport(skill)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function SkillCard({
  skill,
  onEdit,
  onDelete,
  onExport,
}: {
  skill: Skill
  onEdit: () => void
  onDelete: () => void
  onExport: () => void
}) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <p className="font-medium text-slate-100">{skill.name}</p>
            <span className="font-mono text-xs text-slate-500">{skill.id}</span>
            <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-xs text-blue-300">
              v{skill.version}
            </span>
          </div>
          <p className="text-sm text-slate-400">{skill.description}</p>
          {skill.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {skill.tags.map(tag => (
                <span key={tag} className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">
                  #{tag}
                </span>
              ))}
            </div>
          )}
          <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-300">
            {skill.prompt}
          </pre>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
          <button className="btn-secondary text-xs" onClick={onEdit}>Edit</button>
          <button className="btn-secondary text-xs" onClick={onExport}>Export</button>
          <button className="btn-danger text-xs" onClick={onDelete}>Delete</button>
        </div>
      </div>
    </div>
  )
}
