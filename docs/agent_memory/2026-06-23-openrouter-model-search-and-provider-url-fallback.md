# OpenRouter model search and provider URL fallback

Date: 2026-06-23

Context:
- On another PC, chat execution surfaced `'NoneType' object has no attribute 'rstrip'`.
- The Agent form also needed OpenRouter model selection to list the loaded models and support searching before selection.

Findings:
- `Provider.base_url` is optional in the domain schema.
- `ProviderRegistry.get()` passes `provider_config.base_url` directly to provider constructors.
- `OllamaProvider` and `OpenRouterProvider` previously called `base_url.rstrip("/")` without guarding `None`.
- `AgentForm` fetched models through `/api/providers/{id}/models`, but rendered them as a native select, which listed options without search.

Decision:
- Keep provider URL defaults in the provider constructors as the last defensive boundary.
- Keep the existing `/models` API contract and make the frontend model picker filter the full returned list locally.

Verification:
- `cd backend && python -m pytest tests/test_providers.py -v`
- `cd apps/frontend && npm.cmd test -- --run src/__tests__/AgentForm.test.tsx`
