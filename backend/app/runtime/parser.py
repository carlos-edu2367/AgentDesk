import json
import re
from typing import Dict, Any


class ParserResult:
    def __init__(
        self,
        is_final: bool,
        content: str = "",
        is_tool_call: bool = False,
        tool_name: str = "",
        arguments: Dict[str, Any] = None,
    ):
        self.is_final = is_final
        self.content = content
        self.is_tool_call = is_tool_call
        self.tool_name = tool_name
        self.arguments = arguments or {}


class OutputParser:
    _CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

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

        # 3. Fallback: plain text final answer
        return ParserResult(is_final=True, content=text)

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
                tool_name=data.get("tool", "unknown_tool"),
                arguments=data.get("arguments", {}),
            )

        if msg_type == "subagent_call":
            return ParserResult(
                is_final=False,
                is_tool_call=True,
                tool_name="agent.call",
                arguments={
                    "target_agent_id": data.get("target_agent_id", ""),
                    "task": data.get("task", ""),
                    "context": data.get("context", {}),
                },
            )

        return None
