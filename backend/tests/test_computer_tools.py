import pytest
from app.tools.capabilities import CAPABILITIES, CRITICAL_TOOLS, NATIVE_TOOLS
from app.tools.base import ToolExecutionContext


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
