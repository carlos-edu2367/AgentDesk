import json
import re
from typing import Dict, Any, List


class ParserResult:
    def __init__(
        self,
        is_final: bool,
        content: str = "",
        is_tool_call: bool = False,
        tool_name: str = "",
        arguments: Dict[str, Any] = None,
        tool_calls: List[Dict[str, Any]] = None,
        is_batch: bool = False,
    ):
        self.is_final = is_final
        self.content = content
        self.is_tool_call = is_tool_call
        self.tool_calls = tool_calls or []
        if is_tool_call and not self.tool_calls:
            self.tool_calls = [{"id": "call_1", "tool": tool_name, "arguments": arguments or {}}]
        self.tool_name = tool_name or (self.tool_calls[0].get("tool", "") if self.tool_calls else "")
        self.arguments = arguments or (self.tool_calls[0].get("arguments", {}) if self.tool_calls else {})
        self.is_batch = is_batch


class OutputParser:
    _CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    _PROTOCOL_OPENER_RE = re.compile(
        r'\{\s*"type"\s*:\s*"(tool_call|tool_calls|final_answer|subagent_call)"'
    )

    def parse(self, raw_text: str) -> ParserResult:
        text = raw_text.strip()

        # 1. Try raw JSON
        result = self._try_parse_json(text)
        if result:
            return result

        # 2. Try to extract JSON from markdown code block
        match = self._CODE_BLOCK_RE.search(text)
        if match:
            result = self._try_parse_json(match.group(1).strip())
            if result:
                return result

        # 3. Some models leak prose before the JSON or concatenate multiple
        # tool-call objects. Extract the first valid AgentDesk protocol object
        # so the runtime can execute it and feed the result back to the model.
        embedded_calls: List[Dict[str, Any]] = []
        for candidate in self._extract_json_objects(text):
            result = self._try_parse_json(candidate)
            if not result:
                continue
            if result.is_tool_call:
                embedded_calls.extend(result.tool_calls)
                continue
            if not embedded_calls:
                return result
        if embedded_calls:
            return ParserResult(
                is_final=False,
                is_tool_call=True,
                tool_calls=embedded_calls,
                is_batch=len(embedded_calls) > 1,
            )

        # 4. Fallback: plain text final answer
        return ParserResult(is_final=True, content=text)

    def looks_like_truncated_tool_call(self, raw_text: str) -> bool:
        """True when the model started a protocol JSON object but never produced a
        parseable one — typically because the output was cut off by the model's
        max_tokens (common when writing large file contents inline). The runtime
        uses this to feed the model a recovery hint instead of silently treating
        the broken JSON as a plain-text final answer."""
        text = raw_text.strip()
        if not self._PROTOCOL_OPENER_RE.search(text):
            return False
        if not self._has_unterminated_object(text):
            return False
        for candidate in self._extract_json_objects(text):
            if self._try_parse_json(candidate):
                return False
        return True

    def _has_unterminated_object(self, text: str) -> bool:
        depth = 0
        in_string = False
        escape = False
        opened = False
        for char in text:
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
                opened = True
                continue
            if char == "}" and depth > 0:
                depth -= 1
        return opened and (depth > 0 or in_string)

    def _extract_json_objects(self, text: str) -> List[str]:
        objects: List[str] = []
        start = None
        depth = 0
        in_string = False
        escape = False

        for idx, char in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                if depth == 0:
                    start = idx
                depth += 1
                continue

            if char == "}" and depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    objects.append(text[start:idx + 1])
                    start = None

        return objects

    def _try_parse_json(self, text: str) -> ParserResult | None:
        if not (text.startswith("{") and text.endswith("}")):
            return None
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None

        msg_type = data.get("type", "")

        if msg_type == "final_answer":
            return ParserResult(is_final=True, content=data.get("content", ""))

        if msg_type == "tool_call":
            return ParserResult(
                is_final=False,
                is_tool_call=True,
                tool_calls=[self._normalize_tool_call(data, 0)],
            )

        if msg_type == "tool_calls":
            calls = data.get("calls", [])
            if not isinstance(calls, list) or not calls:
                return None
            tool_calls = [
                self._normalize_tool_call(call, idx)
                for idx, call in enumerate(calls)
                if isinstance(call, dict)
            ]
            if not tool_calls:
                return None
            return ParserResult(
                is_final=False,
                is_tool_call=True,
                tool_calls=tool_calls,
                is_batch=True,
            )

        if msg_type == "subagent_call":
            return ParserResult(
                is_final=False,
                is_tool_call=True,
                tool_calls=[self._normalize_subagent_call(data, 0)],
            )

        return None

    def _normalize_tool_call(self, data: Dict[str, Any], index: int) -> Dict[str, Any]:
        return {
            "id": str(data.get("id") or f"call_{index + 1}"),
            "tool": data.get("tool", "unknown_tool"),
            "arguments": data.get("arguments", {}) if isinstance(data.get("arguments", {}), dict) else {},
        }

    def _normalize_subagent_call(self, data: Dict[str, Any], index: int) -> Dict[str, Any]:
        return {
            "id": str(data.get("id") or f"call_{index + 1}"),
            "tool": "agent.call",
            "arguments": {
                "target_agent_id": data.get("target_agent_id", ""),
                "task": data.get("task", ""),
                "context": data.get("context", {}),
            },
        }
