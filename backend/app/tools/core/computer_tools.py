"""BaseTool implementations for computer-use: perceive, click, type, key, scroll."""
import base64

from app.tools.base import BaseTool
from app.tools.core import computer


class ScreenPerceiveTool(BaseTool):
    name = "screen.perceive"
    capability = "computer_use"
    critical = False
    description = "Capture the screen and list interactive UI elements with numeric ids."
    input_schema = {
        "type": "object",
        "properties": {
            "display": {"type": "integer", "default": 0},
            "annotate": {"type": "boolean", "default": True},
        },
    }

    async def execute(self, arguments, context):
        display = arguments.get("display", 0)
        do_annotate = arguments.get("annotate", True)

        cap = computer.capture(display=display)
        els = computer.enumerate_elements(display=display)
        png = cap["png"]

        if do_annotate:
            png = computer.annotate(png, els, cap["scale_x"], cap["scale_y"])

        context.extra["computer_use_last_map"] = {
            e["id"]: {
                "bbox": e["bbox"],
                "origin_x": cap["origin_x"],
                "origin_y": cap["origin_y"],
            }
            for e in els
        }
        context.extra["computer_use_scale"] = (cap["scale_x"], cap["scale_y"])

        return {
            "elements": [
                {"id": e["id"], "role": e["role"], "name": e["name"]}
                for e in els
            ],
            "image_base64": base64.b64encode(png).decode(),
            "display": display,
        }


class ScreenClickTool(BaseTool):
    name = "screen.click"
    capability = "computer_use"
    critical = True
    description = (
        "Click a UI element by element_id (from screen.perceive) "
        "or by raw coordinates (x, y)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "element_id": {"type": "integer"},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "button": {"type": "string", "default": "left"},
            "double": {"type": "boolean", "default": False},
        },
    }

    async def execute(self, arguments, context):
        button = arguments.get("button", "left")
        double = arguments.get("double", False)
        last_map = context.extra.get("computer_use_last_map", {})

        if arguments.get("element_id") is not None:
            el = last_map.get(arguments["element_id"])
            if not el:
                return {
                    "error": (
                        f"element_id {arguments['element_id']} not found in last perceive. "
                        "Run screen.perceive first."
                    )
                }
            l, t, r, b = el["bbox"]
            x = el["origin_x"] + (l + r) // 2
            y = el["origin_y"] + (t + b) // 2
        else:
            sx, sy = context.extra.get("computer_use_scale", (1.0, 1.0))
            x, y = computer.remap(arguments.get("x", 0), arguments.get("y", 0), sx, sy)

        computer.click(x, y, button=button, double=double)
        return {"status": "ok", "x": x, "y": y}


class ScreenTypeTool(BaseTool):
    name = "screen.type"
    capability = "computer_use"
    critical = True
    description = "Type text into the currently focused element."
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def execute(self, arguments, context):
        computer.type_text(arguments["text"])
        return {"status": "ok"}


class ScreenKeyTool(BaseTool):
    name = "screen.key"
    capability = "computer_use"
    critical = True
    description = "Send a keyboard shortcut, e.g. ctrl+c, enter, alt+tab."
    input_schema = {
        "type": "object",
        "properties": {"combo": {"type": "string"}},
        "required": ["combo"],
    }

    async def execute(self, arguments, context):
        computer.press_keys(arguments["combo"])
        return {"status": "ok"}


class ScreenScrollTool(BaseTool):
    name = "screen.scroll"
    capability = "computer_use"
    critical = True
    description = "Scroll the screen. Use direction+amount or dx/dy."
    input_schema = {
        "type": "object",
        "properties": {
            "dx": {"type": "integer", "default": 0},
            "dy": {"type": "integer", "default": 0},
            "direction": {"type": "string", "enum": ["up", "down"]},
            "amount": {"type": "integer", "default": 3},
        },
    }

    async def execute(self, arguments, context):
        dx = arguments.get("dx", 0)
        dy = arguments.get("dy", 0)
        direction = arguments.get("direction")
        if direction == "down":
            dy = -arguments.get("amount", 3)
        elif direction == "up":
            dy = arguments.get("amount", 3)
        computer.scroll(dx, dy)
        return {"status": "ok"}
