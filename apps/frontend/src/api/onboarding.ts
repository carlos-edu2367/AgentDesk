import { api } from './client'

export interface OnboardingState {
  completed: boolean
  has_providers: boolean
}

export const onboardingApi = {
  state: () => api.get<OnboardingState>('/api/onboarding/state'),
  complete: () => api.post('/api/onboarding/complete', {}),
  createOllamaProvider: () => api.post('/api/onboarding/provider/ollama', {}),
  createOpenRouterProvider: (api_key: string) =>
    api.post('/api/onboarding/provider/openrouter', { api_key }),
}
