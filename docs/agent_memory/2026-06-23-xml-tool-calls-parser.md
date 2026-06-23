# XML-wrapped tool calls in chat runtime

Date: 2026-06-23

## Context

Some model outputs in AgentDesk can wrap tool-call payloads in an XML-like block:

```text
<tool_calls>
{"calls":[{"id":"read_index","tool":"filesystem.read","arguments":{"path":"index.html"}}]}
</tool_calls>
```

Before this fix, `OutputParser` did not treat that wrapper as protocol output.
The runtime could classify the whole block as a final text answer, causing raw
tool-call markup to appear in the chat instead of executing the tools.

## Decision

- Backend parser now detects `<tool_calls>...</tool_calls>` and normalizes the
  inner `calls` list into the same `ParserResult.tool_calls` shape used by the
  existing `{"type":"tool_calls"}` protocol.
- Backend parser also tolerates model outputs that start `<tool_calls>` but end
  as an HTML/Markdown code block (`</code></pre>`) instead of emitting the
  closing `</tool_calls>` tag. It extracts the first valid JSON object from the
  wrapper before falling back to plain text.
- Frontend chat grouping now strips the same XML-like protocol block from
  streamed narration, completed `agent_completed` answers, model reasoning, and
  fallback execution results so incomplete or already-streamed markup is not
  rendered as assistant prose or inside the Thinking block.
- Tool permission, workspace scoping, approval, audit, and execution behavior
  remain unchanged; only protocol recognition/sanitization changed.

## Verification

- `python -m pytest backend\tests\test_runtime_tool_call_parsing.py -q`
- `npm.cmd test -- --run src/__tests__/groupEvents.test.ts`
- `npm.cmd test -- --run src/__tests__/ChatComponents.test.tsx`

## Related finding

During broad verification, `tests/test_executions.py::test_execution_sse` still
expected `model_chunk` during SSE replay. The current endpoint intentionally
skips persisted `model_chunk` and `model_reasoning_chunk` events on replay
because token deltas are only useful during live streaming. The test was aligned
to assert `model_completed` plus `execution_completed` for replayed finished
executions.
