# Phase 9 Memory frontend completion

## Context

Tasks 13-15 of `docs/superpowers/plans/2026-06-18-phase9-memory-system.md` were implemented after tasks 1-12 already existed in the working tree.

## What changed

- Added `apps/frontend/src/views/Memory.tsx` for listing, filtering, searching, creating, and soft-deleting memories through the existing `memoriesApi`.
- Registered the Memory route in `apps/frontend/src/App.tsx`.
- Added the Memory sidebar entry and updated the footer phase label in `apps/frontend/src/components/Sidebar.tsx`.
- Added memory timeline labels in `apps/frontend/src/views/ExecutionDetail.tsx`.
- Added `apps/frontend/src/__tests__/Memory.test.tsx`.

## Decisions

- The frontend uses the repository's existing `TopBar`, `LoadingState`, `ErrorState`, `card`, `form-*`, and `btn-*` patterns instead of copying the plan verbatim.
- Search results are rendered from the `MemorySearchResult` payload directly. This avoids depending on the currently loaded memory list containing every search result.
- The backend full suite initially failed in `test_registry_unknown_provider` because the `Provider` schema correctly rejects invalid provider types before `ProviderRegistry.get()` is reached. The test now uses `DomainProvider.model_construct(...)` only for that defensive registry branch, preserving enum validation for normal domain construction.

## Verification

- `npm.cmd run test -- --reporter=verbose src/__tests__/Memory.test.tsx`: 3 passed.
- `npm.cmd run test`: 31 passed.
- `python -m pytest tests/ -v --tb=short`: 168 passed, 1 skipped.
- `npm.cmd run build`: TypeScript and Vite build passed.
