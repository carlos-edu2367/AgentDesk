import { useState } from 'react'
import { onboardingApi } from '../../api/onboarding'
import { WelcomeStep, OllamaStep, OpenRouterStep, DoneStep } from './steps'
import { Logo } from '../Logo'

type Step = 'welcome' | 'ollama' | 'openrouter' | 'done'

export function OnboardingWizard({ onFinished }: { onFinished: () => void }) {
  const [step, setStep] = useState<Step>('welcome')

  const finishSkipped = () => {
    localStorage.setItem('agentdesk.onboardingSkipped', '1')
    onFinished()
  }
  const finishCompleted = async () => {
    await onboardingApi.complete().catch(() => {})
    onFinished()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/95">
      <div className="w-[560px] max-w-[92vw] rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <Logo className="h-7 w-7" />
          <span className="text-sm font-bold text-slate-200">AgentDesk</span>
        </div>
        {step === 'welcome' && (
          <WelcomeStep onChoose={p => {
            if (p === 'skip') finishSkipped()
            else setStep(p)
          }} />
        )}
        {step === 'ollama' && <OllamaStep onDone={() => setStep('done')} />}
        {step === 'openrouter' && <OpenRouterStep onDone={() => setStep('done')} />}
        {step === 'done' && <DoneStep onClose={finishCompleted} />}
      </div>
    </div>
  )
}
