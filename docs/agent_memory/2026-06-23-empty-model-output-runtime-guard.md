# Empty model output runtime guard

## Context

AgentDesk could persist an execution as `completed` with `result = ""` when a model produced useful reasoning/tool activity but no final content. A follow-up like `prossiga` then lost context because `build_conversation_history()` ignores prior turns without a truthy `result`.

## Change

- `backend/app/runtime/agent_runtime.py` now treats a blank model response as a runtime error instead of `agent_completed` with an empty result.
- The error message distinguishes blank output after tool use: `Model returned an empty response after tool use. No final answer or tool call was produced.`
- `backend/app/orchestrator/execution_engine.py` now raises on `EventType.ERROR` from the runtime loop, so `run_agent_execution()` / `resume_agent_execution()` mark the execution failed via the existing `_fail_execution()` path instead of completing with an empty result.
- Regression coverage was added in `backend/tests/test_runtime_tool_call_parsing.py` for both runtime behavior and orchestrator propagation.

## Verification

- `python -m pytest backend\tests\test_runtime_tool_call_parsing.py -q -k "empty_result_after_tool_use or execution_engine_fails_when_runtime_emits_error"` from repo root: `2 passed`.
- `python -m pytest backend\tests\test_runtime_tool_call_parsing.py backend\tests\test_conversations.py -q` from repo root: `23 passed`.
- `python -m pytest tests -q` from `backend`: `328 passed, 1 skipped`.

## Note

Running `python -m pytest backend\tests -q` from the repo root still fails `test_catalog_files_valid` because that test uses the relative glob `resources/skills/base/*.skill.json` and expects cwd `backend`.

