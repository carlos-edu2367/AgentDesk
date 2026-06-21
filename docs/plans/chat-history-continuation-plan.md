# Chat History Continuation Implementation Plan

**Goal:** Add a discoverable chat history so users can reopen previous agent/team conversations and continue with the existing backend conversation context.

**Architecture:** Reuse the existing `/api/conversations` backend, `ConversationModel`, and `ConversationView`. Add a frontend history view plus small entry-point changes in Agents/Teams so the UI opens the latest existing conversation for a target before creating a new one.

**Tech Stack:** React, React Router, Vitest, Testing Library, FastAPI existing conversation API.

---

### Task 1: Conversation History View

**Files:**
- Create: `apps/frontend/src/views/Conversations.tsx`
- Test: `apps/frontend/src/__tests__/Conversations.test.tsx`
- Modify: `apps/frontend/src/App.tsx`
- Modify: `apps/frontend/src/components/Sidebar.tsx`

- [ ] Write a failing test that mocks `conversationsApi.list`, renders `/conversations`, and expects recent conversation titles plus an Open action.
- [ ] Run `npm test -- --run src/__tests__/Conversations.test.tsx` in `apps/frontend` and verify it fails because the view does not exist.
- [ ] Implement `Conversations.tsx` using `TopBar`, `LoadingState`, `EmptyState`, and `ErrorState`.
- [ ] Add route `conversations` to `App.tsx`.
- [ ] Add `Chats` to the sidebar.
- [ ] Re-run the focused test and verify it passes.

### Task 2: Continue Existing Chats From Agents

**Files:**
- Modify: `apps/frontend/src/views/Agents.tsx`
- Test: `apps/frontend/src/__tests__/Agents.test.tsx`

- [ ] Add a failing test that clicks `Chat`, expects `conversationsApi.list({ type: 'agent', target_id: 'agent_001' })`, and expects navigation to the latest returned conversation.
- [ ] Run `npm test -- --run src/__tests__/Agents.test.tsx` in `apps/frontend` and verify it fails because the current code creates a new chat directly.
- [ ] Update `handleChat` to list existing conversations first, navigate to the first returned conversation, and create only when none exist.
- [ ] Re-run the focused test and verify it passes.

### Task 3: Continue Existing Chats From Teams

**Files:**
- Modify: `apps/frontend/src/views/Teams.tsx`
- Test: `apps/frontend/src/__tests__/Teams.test.tsx`

- [ ] Add a failing test for the team `Chat` button that verifies latest team conversation reuse.
- [ ] Run `npm test -- --run src/__tests__/Teams.test.tsx` in `apps/frontend` and verify it fails with the current create-first behavior.
- [ ] Update `handleChatTeam` to reuse the latest conversation before creating a new one.
- [ ] Re-run the focused test and verify it passes.

### Task 4: Verification And Memory

**Files:**
- Create: `docs/agent_memory/YYYY-MM-DD-chat-history-continuation.md`

- [ ] Run focused frontend tests for conversations, agents, and teams.
- [ ] Run `npm run build` in `apps/frontend`.
- [ ] Save a technical memory under `docs/agent_memory` describing the existing backend conversation context and the new frontend reuse behavior.
