# Embedded tool-call parsing

## Context

The chat runtime can receive model output that mixes prose with AgentDesk tool-call JSON, or concatenates more than one JSON object in a single model response.

Example shape:

```text
Vou pesquisar para voce.{"type":"tool_call","tool":"http.request","arguments":{...}}{"type":"tool_call","tool":"http.request","arguments":{...}}
```

## What existed

- `AgentRuntime` already supports a multi-step loop: after a parsed tool call, it executes the tool, appends a `tool_result` message, and calls the model again.
- `OutputParser` only parsed protocol JSON when the entire response was a JSON object or when the first markdown code block contained valid protocol JSON.
- The frontend grouping already avoids rendering streamed tool-call JSON as the assistant answer when a real tool-call event exists.

## Decision

`OutputParser` now scans the raw model output for balanced JSON objects and accepts the first valid AgentDesk protocol object. This lets the runtime identify a tool call even when the model adds text before it or emits more JSON afterward.

The runtime loop remains responsible for feeding each tool result back to the model before the model decides whether to call another tool or return a final answer.

The preferred multi-tool protocol is now:

```json
{
  "type": "tool_calls",
  "calls": [
    {"id": "call_1", "tool": "http.request", "arguments": {"url": "https://example.com/a"}},
    {"id": "call_2", "tool": "http.request", "arguments": {"url": "https://example.com/b"}}
  ]
}
```

For a batch, `AgentRuntime` executes each call through the same permission, approval, audit, plugin, MCP, and error paths used by single calls. It then sends one model-visible message:

```json
{
  "type": "tool_results",
  "results": [
    {"id": "call_1", "tool": "http.request", "status": "success", "result": {}},
    {"id": "call_2", "tool": "http.request", "status": "success", "result": {}}
  ]
}
```

If the model still lacks coherent context after reading `tool_results`, it can return another `tool_call` or `tool_calls` before the final answer.

## Reasoning

The root bug was parser coverage, not the tool execution loop. Treating the mixed output as a final answer caused the UI to show raw JSON and prevented the tool result from being returned to the model.

The safer invariant is one model decision per step, with one or more tool calls inside that decision. Tool execution stays backend-authoritative and keeps tenant/workspace, permission, audit, and approval checks per individual tool call.

Manual approval still pauses execution at the first pending critical tool in the batch, preserving the existing approval resume model instead of auto-running later calls before human review.

## Verification

- `python -m pytest backend\tests\test_runtime_tool_call_parsing.py -q`
- `python -m pytest backend\tests\test_runtime_tool_call_parsing.py backend\tests\test_runtime_tool_result_compaction.py backend\tests\test_phase10_subagents.py -q`
- `npm.cmd test -- --run src/__tests__/groupEvents.test.ts`
