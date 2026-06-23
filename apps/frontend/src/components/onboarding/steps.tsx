import { useEffect, useState } from 'react'
import { ollamaApi, type ProgressEvent, type Recommendations, type ModelEntry } from '../../api/ollama'
import { onboardingApi } from '../../api/onboarding'

export function WelcomeStep({ onChoose }: { onChoose: (p: 'ollama' | 'openrouter' | 'skip') => void }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100">Bem-vindo ao AgentDesk</h2>
        <p className="text-sm text-slate-400 mt-1">
          Para rodar agentes você precisa de pelo menos um provedor de modelos. Escolha um abaixo —
          você pode trocar depois nas Configurações.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="card">
          <p className="font-medium text-slate-100">Ollama</p>
          <p className="text-xs text-slate-400 mt-1">Local · grátis · privado. Usa a RAM/GPU da sua máquina. Instalável aqui pelo app.</p>
          <button className="btn-primary text-sm mt-3 w-full" onClick={() => onChoose('ollama')}>Configurar Ollama</button>
        </div>
        <div className="card">
          <p className="font-medium text-slate-100">OpenRouter</p>
          <p className="text-xs text-slate-400 mt-1">Nuvem · precisa de API key · pago. Nada para instalar.</p>
          <button className="btn-secondary text-sm mt-3 w-full" onClick={() => onChoose('openrouter')}>Usar OpenRouter</button>
        </div>
      </div>
      <button className="btn-ghost text-xs text-slate-500" onClick={() => onChoose('skip')}>Pular por enquanto</button>
    </div>
  )
}

function ProgressBar({ ev }: { ev: ProgressEvent | null }) {
  const pct = ev?.percent ?? null
  return (
    <div className="space-y-1">
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div className="h-full bg-blue-500 transition-all" style={{ width: pct != null ? `${pct}%` : '100%' }} />
      </div>
      <p className="text-xs text-slate-400">{ev?.message ?? ''}{pct != null ? ` (${pct}%)` : ''}</p>
    </div>
  )
}

export function OllamaStep({ onDone }: { onDone: () => void }) {
  const [phase, setPhase] = useState<'checking' | 'needs-install' | 'installing' | 'ready' | 'pulling' | 'error'>('checking')
  const [progress, setProgress] = useState<ProgressEvent | null>(null)
  const [recs, setRecs] = useState<Recommendations | null>(null)
  const [selected, setSelected] = useState<string>('')
  const [errorEv, setErrorEv] = useState<ProgressEvent | null>(null)

  const loadReady = async () => {
    const r = await ollamaApi.recommendations()
    setRecs(r)
    setSelected(r.models[0]?.tag ?? '')
    setPhase('ready')
  }

  useEffect(() => {
    ollamaApi.status().then(s => {
      if (s.running) loadReady()
      else setPhase('needs-install')
    }).catch(() => setPhase('needs-install'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const runInstall = async () => {
    setPhase('installing'); setErrorEv(null)
    for await (const ev of ollamaApi.install()) {
      setProgress(ev)
      if (ev.phase === 'error') { setErrorEv(ev); setPhase('error'); return }
      if (ev.phase === 'done') { await loadReady(); return }
    }
  }

  const runPull = async () => {
    if (!selected) return
    setPhase('pulling'); setErrorEv(null)
    for await (const ev of ollamaApi.pull(selected)) {
      setProgress(ev)
      if (ev.phase === 'error') { setErrorEv(ev); setPhase('error'); return }
      if (ev.phase === 'success') {
        await onboardingApi.createOllamaProvider()
        onDone(); return
      }
    }
  }

  if (phase === 'checking') return <p className="text-sm text-slate-400">Verificando o Ollama…</p>

  if (phase === 'needs-install' || phase === 'installing') {
    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-300">O Ollama ainda não está rodando. Instale-o pelo app:</p>
        {phase === 'installing' ? <ProgressBar ev={progress} /> :
          <button className="btn-primary text-sm" onClick={runInstall}>Instalar Ollama</button>}
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-400">{errorEv?.message ?? 'Algo deu errado.'}</p>
        <div className="flex gap-2">
          <button className="btn-secondary text-sm" onClick={runInstall}>Tentar novamente</button>
          {errorEv?.manual_url && (
            <a className="btn-ghost text-sm" href={errorEv.manual_url} target="_blank" rel="noreferrer">Baixar manualmente</a>
          )}
        </div>
        {errorEv?.winget && (
          <code className="block text-xs bg-slate-800 rounded px-2 py-1 text-slate-300">{errorEv.winget}</code>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {recs && (
        <div className="card text-xs text-slate-400">
          Hardware: {recs.hardware.ram_gb} GB RAM · {recs.hardware.cpu_cores} núcleos
          {recs.hardware.gpu_name ? ` · ${recs.hardware.gpu_name}` : ''}
          {recs.hardware.vram_gb ? ` (${recs.hardware.vram_gb} GB VRAM)` : ''}
        </div>
      )}
      <p className="text-sm text-slate-300">Modelos recomendados para sua máquina (tier {recs?.tier_label}):</p>
      <div className="space-y-2">
        {recs?.models.map((m: ModelEntry) => (
          <label key={m.tag} className={`card flex items-start gap-3 cursor-pointer ${selected === m.tag ? 'ring-1 ring-blue-500' : ''}`}>
            <input type="radio" name="model" className="mt-1" checked={selected === m.tag} onChange={() => setSelected(m.tag)} />
            <div className="min-w-0">
              <p className="font-medium text-slate-100">{m.label} <span className="text-xs text-slate-500">{m.params} · {m.approx_size_gb} GB{m.vision ? ' · visão' : ''}</span></p>
              <p className="text-xs text-slate-400">{m.blurb}</p>
            </div>
          </label>
        ))}
      </div>
      {phase === 'pulling' ? <ProgressBar ev={progress} /> :
        <button className="btn-primary text-sm" onClick={runPull} disabled={!selected}>Instalar modelo selecionado</button>}
    </div>
  )
}

export function OpenRouterStep({ onDone }: { onDone: () => void }) {
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submit = async () => {
    setBusy(true); setError(null)
    try { await onboardingApi.createOpenRouterProvider(key); onDone() }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-300">Cole sua API key do OpenRouter:</p>
      <input type="password" className="form-input" placeholder="sk-or-..." value={key}
        onChange={e => setKey(e.target.value)} />
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button className="btn-primary text-sm" onClick={submit} disabled={busy || !key}>{busy ? 'Salvando…' : 'Salvar e continuar'}</button>
    </div>
  )
}

export function DoneStep({ onClose }: { onClose: () => void }) {
  return (
    <div className="space-y-4 text-center">
      <p className="text-lg font-bold text-slate-100">Tudo pronto!</p>
      <p className="text-sm text-slate-400">Seu provedor está configurado. Vamos começar a conversar.</p>
      <button className="btn-primary text-sm" onClick={onClose}>Ir para o chat</button>
    </div>
  )
}
