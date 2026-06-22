# Chat history sidebar-only

## Context

The app already has a global conversation history in `apps/frontend/src/components/Sidebar.tsx`.
`apps/frontend/src/views/ConversationView.tsx` also rendered a second per-agent/team history rail inside the chat.

## Decision

The chat view should not fetch or render sibling conversations. Conversation navigation/history belongs to the layout sidebar only.

## Change

Removed the `ConversationView` sibling conversation state, the `conversationsApi.list({ type, target_id, limit: 100 })` call, and the internal history rail/new-chat block.

## Verification

Added a regression test in `apps/frontend/src/__tests__/ConversationView.test.tsx` asserting that the chat view does not fetch or render an internal conversation history rail.
