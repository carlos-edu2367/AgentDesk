"""
Native computer-use layer: screen capture, UIA element enumeration,
set-of-marks annotation, mouse/keyboard actuation. Windows-only.
"""
import ctypes
import sys

# --- DPI awareness (call once at import) ---

def _set_dpi_aware():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

_set_dpi_aware()

# --- Coordinate helpers ---

def remap(x: int, y: int, scale_x: float, scale_y: float) -> tuple:
    """Convert model-space coords (downscaled image) back to real pixels."""
    return (round(x / scale_x), round(y / scale_y))


def parse_combo(combo: str) -> list:
    """'ctrl+c' -> ['ctrl', 'c']"""
    return [k.strip().lower() for k in combo.split("+") if k.strip()]


# --- Screen capture ---

def compute_downscale(w: int, h: int, max_side: int = 1568):
    """Returns (new_w, new_h, scale_x, scale_y). scale=1 when already small."""
    longest = max(w, h)
    if longest <= max_side:
        return (w, h, 1.0, 1.0)
    s = max_side / longest
    return (round(w * s), round(h * s), s, s)


def capture(display: int = 0, max_side: int = 1568) -> dict:
    """
    Grab screenshot of the given monitor (0-indexed physical monitors).
    Returns dict with png bytes, scale factors, real dimensions, and monitor origin.
    """
    import io
    import mss
    from PIL import Image

    with mss.mss() as sct:
        # monitors[0] = all; [1..n] = individual physical monitors
        idx = display + 1
        if idx >= len(sct.monitors):
            idx = 1
        mon = sct.monitors[idx]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    nw, nh, sx, sy = compute_downscale(img.width, img.height, max_side)
    if (nw, nh) != (img.width, img.height):
        img = img.resize((nw, nh))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {
        "png": buf.getvalue(),
        "scale_x": sx,
        "scale_y": sy,
        "real_w": mon["width"],
        "real_h": mon["height"],
        "origin_x": mon["left"],
        "origin_y": mon["top"],
    }


# --- UIA element enumeration ---

_INTERACTIVE = frozenset({
    "Button", "Edit", "CheckBox", "RadioButton", "ComboBox",
    "MenuItem", "ListItem", "Hyperlink", "TabItem", "Slider",
    "SplitButton", "ToggleButton",
})


def filter_elements(raw: list, max_count: int = 80) -> list:
    """Keep only interactive, visible elements; assign synthetic ids 0..N."""
    kept = [e for e in raw if e.get("visible") and e.get("role") in _INTERACTIVE]
    kept.sort(key=lambda e: e.get("area", 0), reverse=True)
    kept = kept[:max_count]
    for i, e in enumerate(kept):
        e["id"] = i
    return kept


def _walk(ctrl, max_depth, depth=0):
    if ctrl is None or depth > max_depth:
        return
    yield ctrl, depth
    try:
        for child in ctrl.GetChildren():
            yield from _walk(child, max_depth, depth + 1)
    except Exception:
        return


def enumerate_elements(display: int = 0, max_count: int = 80) -> list:
    """Return interactive elements from the foreground window via Windows UIA."""
    import uiautomation as auto

    raw = []
    try:
        root = auto.GetForegroundControl()
        for ctrl, _depth in _walk(root, max_depth=25):
            try:
                r = ctrl.BoundingRectangle
                if r.width() <= 0 or r.height() <= 0:
                    continue
                raw.append({
                    "role": ctrl.ControlTypeName.replace("Control", ""),
                    "name": (ctrl.Name or "")[:80],
                    "bbox": (r.left, r.top, r.right, r.bottom),
                    "visible": not ctrl.IsOffscreen,
                    "enabled": ctrl.IsEnabled,
                    "area": r.width() * r.height(),
                })
            except Exception:
                continue
    except Exception:
        pass

    return filter_elements(raw, max_count)


# --- Annotation (set-of-marks) ---

def annotate(png: bytes, elements: list, scale_x: float, scale_y: float) -> bytes:
    """Draw numbered bounding boxes over the screenshot PNG."""
    import io
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(png)).convert("RGB")
    d = ImageDraw.Draw(img)

    for e in elements:
        l, t, r, b = e["bbox"]
        box = (l * scale_x, t * scale_y, r * scale_x, b * scale_y)
        d.rectangle(box, outline=(255, 0, 0), width=2)
        d.text((box[0] + 2, box[1] + 2), str(e["id"]), fill=(255, 0, 0))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# --- Actuation (lazy-init controllers) ---

_mouse = None
_keyboard = None


def _kb():
    global _keyboard
    if _keyboard is None:
        from pynput.keyboard import Controller
        _keyboard = Controller()
    return _keyboard


def _ms():
    global _mouse
    if _mouse is None:
        from pynput.mouse import Controller
        _mouse = Controller()
    return _ms


def _to_key(name: str):
    from pynput.keyboard import Key
    if hasattr(Key, name):
        return getattr(Key, name)
    return name


def press_keys(combo: str):
    kb = _keyboard or _kb()
    keys = parse_combo(combo)
    for k in keys:
        kb.press(_to_key(k))
    for k in reversed(keys):
        kb.release(_to_key(k))


def click(x: int, y: int, button: str = "left", double: bool = False):
    from pynput.mouse import Button
    ms = _mouse or _ms()
    ms.position = (x, y)
    ms.click(getattr(Button, button, Button.left), 2 if double else 1)


def type_text(text: str):
    (_keyboard or _kb()).type(text)


def scroll(dx: int, dy: int):
    ms = _mouse or _ms()
    ms.scroll(dx, dy)
