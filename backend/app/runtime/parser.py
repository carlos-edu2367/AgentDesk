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
    _XML_TOOL_CALLS_RE = re.compile(
        r"<tool_calls>\s*([\s\S]*?)(?:</tool_calls>|</code>|</pre>|$)",
        re.IGNORECASE,
    )
    _PROTOCOL_OPENER_RE = re.compile(
        r'\{\s*"type"\s*:\s*"(tool_call|tool_calls|final_answer|subagent_call)"|<tool_calls>'
    )
    # Matches: <|tool_call>call:tool.name{key:<|">val<|">}<tool_call>
    # Emitted by some local/fine-tuned models that use special-token delimiters
    # instead of the JSON protocol taught in the system prompt.
    _TAG_TOOL_RE = re.compile(
        r"<\|tool_call\>\s*call:([a-z_][a-z0-9_.]*)\s*\{(.*?)\}\s*<\|?/?tool_call\>?",
        re.DOTALL | re.IGNORECASE,
    )
    # Matches a single argument inside the tag-format arg block.
    # Group 1+2: quoted with <|"> or " delimiters; group 3+4: bare (unquoted) value.
    _TAG_ARG_RE = re.compile(
        r'([a-z_][a-z0-9_]*)\s*:\s*(?:<\|"\>|")(.*?)(?:<\|"\>|")'
        r'|([a-z_][a-z0-9_]*)\s*:\s*([^,}\s]+)',
        re.DOTALL,
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

        match = self._XML_TOOL_CALLS_RE.search(text)
        if match:
            result = self._try_parse_xml_tool_calls(match.group(1).strip())
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

        # 4. <|tool_call>call:name{args}<tool_call> — special-token format used by
        # some local/fine-tuned models instead of the JSON protocol.
        result = self._try_parse_tag_tool_call(text)
        if result:
            return result

        # 5. Fallback: plain text final answer
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

        # Lenient fallbacks: smaller/local models routinely drift from the exact
        # protocol when emitting a tool call. Accept the common deviations so the
        # call actually executes instead of being dropped and leaking raw JSON
        # into the chat. The runtime still validates the tool name afterwards, so
        # a genuine mistake surfaces as a visible tool error, not silence.
        args = data.get("arguments")
        if not isinstance(args, dict):
            args = data.get("args") if isinstance(data.get("args"), dict) else None
        if args is not None:
            # Shape: {"tool"/"name": "<tool>", "arguments": {...}} (type missing
            # or unrecognized).
            tool_field = data.get("tool") or data.get("name")
            if isinstance(tool_field, str) and tool_field:
                return ParserResult(
                    is_final=False,
                    is_tool_call=True,
                    tool_calls=[{
                        "id": str(data.get("id") or "call_1"),
                        "tool": tool_field,
                        "arguments": args,
                    }],
                )
            # Shape: {"type": "<tool.name>", "arguments": {...}} — the tool name
            # was collapsed into `type`. A dotted name is our tool-naming
            # convention (filesystem.write, memory.create, …), so it's a strong,
            # low-false-positive signal.
            if isinstance(msg_type, str) and "." in msg_type:
                return ParserResult(
                    is_final=False,
                    is_tool_call=True,
                    tool_calls=[{
                        "id": str(data.get("id") or "call_1"),
                        "tool": msg_type,
                        "arguments": args,
                    }],
                )

        # Shape: {"type": "<tool.name>", "path": "...", ...} — arguments inlined at
        # root with no "arguments" wrapper. Some local models skip the wrapper
        # entirely and put the tool params directly alongside "type".
        if isinstance(msg_type, str) and "." in msg_type:
            inline_args = {k: v for k, v in data.items() if k not in ("type", "id")}
            return ParserResult(
                is_final=False,
                is_tool_call=True,
                tool_calls=[{
                    "id": str(data.get("id") or "call_1"),
                    "tool": msg_type,
                    "arguments": inline_args,
                }],
            )

        return None

    def _try_parse_xml_tool_calls(self, text: str) -> "ParserResult | None":
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            data = None
            for candidate in self._extract_json_objects(text):
                try:
                    parsed = json.loads(candidate)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(parsed, dict):
                    data = parsed
                    break
            if data is None:
                return None
        if not isinstance(data, dict):
            return None

        if data.get("type") in {"tool_call", "tool_calls", "subagent_call"}:
            return self._try_parse_json(json.dumps(data))

        calls = data.get("calls")
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

    def _try_parse_tag_tool_call(self, text: str) -> "ParserResult | None":
        m = self._TAG_TOOL_RE.search(text)
        if not m:
            return None
        tool = m.group(1)
        args_text = m.group(2)
        arguments: Dict[str, Any] = {}
        for am in self._TAG_ARG_RE.finditer(args_text):
            if am.group(1) is not None:
                arguments[am.group(1)] = am.group(2)
            elif am.group(3) is not None:
                arguments[am.group(3)] = am.group(4)
        return ParserResult(
            is_final=False,
            is_tool_call=True,
            tool_calls=[{"id": "call_1", "tool": tool, "arguments": arguments}],
        )

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
