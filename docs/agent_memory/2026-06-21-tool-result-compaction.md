# Tool result compaction after HTTP calls

## Context

In agent conversations, a model can call `http.request` and then fail to produce a final answer after the tool completes.

## What exists

- `AgentRuntime` executes multi-step tool loops and should call the model again after a `tool_result`.
- `http.request` can return up to 200,000 characters in `body`.
- Runtime events and audit previews are truncated separately, but the model continuation previously received the raw tool result.

## Decision

Tool results sent back to the model are now compacted with `_compact_tool_result_for_model`.

The persisted tool events, result previews, and audit logging remain unchanged. Only the prompt payload for the next model step is reduced.

## Reasoning

Large HTTP bodies, especially search result HTML, can make the second provider request too large or slow. That leaves the chat showing the tool call without a final assistant answer.

For chat rendering, `groupTurnEvents` no longer shows streamed tool-call JSON as the assistant answer when the turn contains a real tool call. It waits for `agent_completed`.

## Verification

- `python -m pytest backend\tests\test_runtime_tool_result_compaction.py -q`
- `npm.cmd test -- --run src/__tests__/groupEvents.test.ts`
