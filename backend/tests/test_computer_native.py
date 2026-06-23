from app.tools.core import computer


def test_press_keys_maps_combo(monkeypatch):
    events = []

    class FakeKb:
        def press(self, k):
            events.append(("press", k))

        def release(self, k):
            events.append(("release", k))

    monkeypatch.setattr(computer, "_keyboard", FakeKb())
    computer.press_keys("ctrl+a")

    ops = [op for op, _ in events]
    keys = [k for _, k in events]

    # 2 presses, then 2 releases
    assert ops == ["press", "press", "release", "release"]
    # single key: just press + release
    single_events = []
    monkeypatch.setattr(computer, "_keyboard", FakeKb())

    class TrackKb:
        def __init__(self): self.evts = []
        def press(self, k): self.evts.append(("press", k))
        def release(self, k): self.evts.append(("release", k))

    kb2 = TrackKb()
    monkeypatch.setattr(computer, "_keyboard", kb2)
    computer.press_keys("enter")
    assert len(kb2.evts) == 2
    assert kb2.evts[0][0] == "press"
    assert kb2.evts[1][0] == "release"


def test_filter_keeps_interactive_visible_and_caps_count():
    raw = [
        {"role": "Button", "name": "OK", "bbox": (0, 0, 50, 20), "visible": True, "enabled": True, "area": 1000},
        {"role": "Text", "name": "label", "bbox": (0, 0, 10, 10), "visible": True, "enabled": True, "area": 100},
        {"role": "Button", "name": "Hidden", "bbox": (0, 0, 1, 1), "visible": False, "enabled": True, "area": 1},
    ]
    out = computer.filter_elements(raw, max_count=80)
    roles = [e["role"] for e in out]
    assert "Text" not in roles
    assert "OK" in [e["name"] for e in out]
    assert all(e["visible"] for e in out)
    assert out[0]["id"] == 0


def test_compute_downscale_keeps_aspect_and_factor():
    w, h, sx, sy = computer.compute_downscale(3000, 2000, max_side=1568)
    assert w == 1568
    assert sx == sy
    assert round(sx, 4) == round(1568 / 3000, 4)


def test_compute_downscale_noop_when_small():
    assert computer.compute_downscale(800, 600, max_side=1568) == (800, 600, 1.0, 1.0)


def test_remap_scales_model_coords_to_real_pixels():
    assert computer.remap(100, 50, scale_x=0.5, scale_y=0.5) == (200, 100)


def test_parse_combo_splits_modifiers():
    assert computer.parse_combo("ctrl+c") == ["ctrl", "c"]
    assert computer.parse_combo("enter") == ["enter"]
