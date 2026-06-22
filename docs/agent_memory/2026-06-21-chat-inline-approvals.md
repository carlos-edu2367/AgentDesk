# Chat inline approvals and auto-approval

Date: 2026-06-21

## Context

The chat UI could show raw `approval_requested` and `execution_waiting_approval`
events in the logs, but did not expose an inline approval action in the assistant
turn. The chat send payload also did not choose an approval mode, so the backend
defaulted to manual approval even when the user wanted auto-approval in chat.

## Existing contract found

- `ConversationMessageRequest` already supports `approval_mode`.
- The conversation message endpoint already forwards `approval_mode` into the
  execution creation request.
- `approvalsApi.resolve(executionId, approvalId, approved, reason?)` already
  calls the existing execution approval route.
- The backend remains the source of truth for permission checks, approval
  creation, approval resolution, and execution resume.

## Implemented behavior

- `groupTurnEvents` now derives `pendingApproval` from `approval_requested` and
  `execution_waiting_approval`, and clears it on approval resolution events.
- Tool lifecycle grouping now prefers call ids (`id` or `call_id`) when present,
  so multiple calls to the same tool in one turn do not collapse into the wrong
  card.
- `AssistantTurn` renders an inline approval card with approve/reject actions.
- `ChatThread` binds the inline approval to the owning execution id.
- `ConversationView` sends `approval_mode: 'manual'` by default and exposes an
  explicit `Auto-approval` checkbox that sends `approval_mode: 'auto'`.

## Validation

- `npm.cmd test -- --run src/__tests__/ChatComponents.test.tsx src/__tests__/ConversationView.test.tsx src/__tests__/groupEvents.test.ts`
  passed with 28 tests.

## Security note

Auto-approval is only a frontend preference sent to the existing backend
execution contract. It does not bypass backend permission, risk, audit, or tool
execution checks.
