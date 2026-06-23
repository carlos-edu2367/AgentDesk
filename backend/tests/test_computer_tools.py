import pytest
from app.tools.capabilities import CAPABILITIES, CRITICAL_TOOLS, NATIVE_TOOLS
from app.tools.base import ToolExecutionContext


class FakeCtx:
    def __init__(self):
        self.extra = {}
        self.execution_id = "e"
        self.agent_id = "a"
        self.workspace_ids = []
        self.db = None
        self.approval_mode = "auto"


def test_computer_use_capability_registered():
    assert "screen.click" in CAPABILITIES["computer_use"]
    assert "screen.perceive" in CAPABILITIES["computer_use"]
    assert "screen.type" in CAPABILITIES["computer_use"]
    assert "screen.key" in CAPABILITIES["computer_use"]
    assert "screen.scroll" in CAPABILITIES["computer_use"]


def test_actuators_are_critical_perceive_is_not():
    assert "screen.click" in CRITICAL_TOOLS
    assert "screen.type" in CRITICAL_TOOLS
    assert "screen.key" in CRITICAL_TOOLS
    assert "screen.scroll" in CRITICAL_TOOLS
    assert "screen.perceive" not in CRITICAL_TOOLS


def test_computer_use_never_native():
    assert not (NATIVE_TOOLS & set(CAPABILITIES["computer_use"]))


@pytest.mark.asyncio
async def test_perceive_returns_elements_and_image(monkeypatch):
    from app.tools.core import computer_tools
    from app.tools.core import computer

    monkeypatch.setattr(
        computer, "capture",
        lambda display=0, max_side=1568: {
            "png": b"PNG", "scale_x": 1.0, "scale_y": 1.0,
            "real_w": 100, "real_h": 100, "origin_x": 0, "origin_y": 0,
        }
    )
    monkeypatch.setattr(
        computer, "enumerate_elements",
        lambda display=0, max_count=80: [
            {"id": 0, "role": "Button", "name": "OK", "bbox": (0, 0, 50, 20)},
        ]
    )
    monkeypatch.setattr(computer, "annotate", lambda *a, **k: b"ANNOTATED")

    ctx = FakeCtx()
    out = await computer_tools.ScreenPerceiveTool().execute({"display": 0}, ctx)

    assert any(e["name"] == "OK" for e in out["elements"])
    assert "image_base64" in out
    assert ctx.extra["computer_use_last_map"][0]["bbox"] == (0, 0, 50, 20)


@pytest.mark.asyncio
async def test_click_by_element_id_uses_center_real_pixels(monkeypatch):
    from app.tools.core import computer_tools
    from app.tools.core import computer

    clicks = []
    monkeypatch.setattr(
        computer, "click",
        lambda x, y, button="left", double=False: clicks.append((x, y))
    )

    ctx = FakeCtx()
    ctx.extra["computer_use_last_map"] = {
        0: {"bbox": (10, 10, 30, 50), "origin_x": 0, "origin_y": 0}
    }

    out = await computer_tools.ScreenClickTool().execute({"element_id": 0}, ctx)
    assert out.get("status") == "ok"
    assert clicks == [(20, 30)]


@pytest.mark.asyncio
async def test_click_invalid_element_id_returns_error():
    from app.tools.core import computer_tools

    ctx = FakeCtx()
    ctx.extra["computer_use_last_map"] = {}
    out = await computer_tools.ScreenClickTool().execute({"element_id": 9}, ctx)
    assert out.get("error")
