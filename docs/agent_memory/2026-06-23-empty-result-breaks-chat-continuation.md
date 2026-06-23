# Empty result breaks chat continuation

## Context

An AgentDesk chat turn asked an agent to create a web TCG project. The agent used tools, read project files, then the user sent `prossiga`. The next turn answered as if there was no previous context.

## Evidence

- Both turns were in the same conversation: `conversation_7e8146395f564edf9a7a1480d05c30be`.
- First turn: `execution_abed9016f5ea48b2a6670f3296916a7c`, status `completed`, `result_len = 0`.
- Second turn: `execution_210fa479c44347d59fc6cf9fad5afb93`, user input `prossiga`, status `completed`.
- The first turn emitted 14 tool calls and completed after a final provider stream where tokens arrived only as `model_reasoning_chunk`; the final `model_completed.raw_output` was empty.
- Runtime then emitted `agent_completed.result = ""` and `execution_completed.result = ""`.
- `backend/app/runtime/history.py` only includes previous executions where `r.result` is truthy, so the empty-result first turn was skipped when building the second turn history.
- The second turn `prompt_built` contained only the system message and user message `prossiga`; the original project request was not present as conversation history.

## Practical diagnosis

This is not primarily a UI rendering issue. The backend persisted a completed execution with an empty result, and the history builder intentionally ignores that turn. A follow-up like `prossiga` therefore reaches the model without the prior task.

## Future fix direction

Consider protecting the runtime against blank final completions after tool use. Options to evaluate:

- If `final_text.strip()` is empty and prior `model_reasoning_chunk` exists, do not persist a successful empty `agent_completed`.
- Retry with a compact user message asking for a valid final answer or next tool call.
- Store enough turn context for continuation even when `result` is empty, possibly from `execution.user_input` plus a summarized event/tool history.
- Add a regression test where a completed prior execution has empty result after tool use and a follow-up message should still receive useful context or the previous turn should be marked failed/incomplete.

