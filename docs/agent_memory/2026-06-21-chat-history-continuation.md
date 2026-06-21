# Chat History Continuation

Date: 2026-06-21

## What exists

- Backend conversations already persisted in `ConversationModel`.
- `ExecutionModel.conversation_id` links each turn execution to a conversation.
- `POST /api/conversations/{id}/messages` creates a new execution in the same conversation.
- Runtime history already uses the conversation id via `build_conversation_history`, so continuing an existing conversation preserves prior user/assistant turns for model context.

## Change made

- Added a frontend `Chats` history page at `/conversations`.
- The page uses the existing `conversationsApi.list({ limit: 100 })` endpoint and opens `/conversations/:id`.
- Agent and team `Chat` actions now query the latest existing conversation for that target before creating a new one.
- If a conversation exists, the UI navigates to it; otherwise it creates a new conversation as before.

## Verification

- `npm test -- --run src/__tests__/Conversations.test.tsx src/__tests__/Agents.test.tsx src/__tests__/Teams.test.tsx`
- `npm run build`
