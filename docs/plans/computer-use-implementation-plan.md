# Computer Use Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que um agente do AgentDesk veja a tela do PC do usuário (screenshot + acessibilidade UIA) e a controle (mouse/teclado) como um humano, ativado explicitamente por chat.

**Architecture:** Grounding híbrido — a árvore UI Automation do Windows entrega elementos com bounding box (clique por id), com fallback para coordenadas visuais a partir de screenshot anotado. Os tools de atuação são `critical` e usam o approval flow existente. Modelo de visão configurável por agente. Três fases sequenciais: A (imagens até o modelo), B (camada nativa + tools `screen.*`), C (loop perceber→agir + ativação por chat).

**Tech Stack:** Python/FastAPI, Pydantic, SQLAlchemy + Alembic, `mss`, `Pillow`, `pynput`, `uiautomation` (Windows UIA via comtypes), Ollama/OpenRouter providers, React/Vite frontend, pytest.

**Specs:** [08-overview](../specs/08-computer-use-overview.md) · [09-fase A](../specs/09-computer-use-vision-pipeline.md) · [10-fase B](../specs/10-computer-use-perception-tools.md) · [11-fase C](../specs/11-computer-use-loop-activation.md)

---

## File Structure

**Fase A — pipeline de visão**
- Modify: `backend/app/providers/schemas.py` — `ImagePart`, `ChatMessage.images`, `ModelInfo.supports_vision`.
- Modify: `backend/app/providers/ollama.py` — helper `_msg_to_ollama`, `supports_vision` em `list_models`.
- Modify: `backend/app/providers/openrouter.py` — helper `_msg_to_openrouter`.
- Test: `backend/tests/providers/test_vision_payloads.py`.

**Fase B — camada nativa + tools**
- Create: `backend/app/tools/core/computer.py` — captura, UIA, atuação, anotação (Windows).
- Create: `backend/app/tools/core/computer_tools.py` — `Screen*Tool(BaseTool)`.
- Modify: `backend/app/tools/capabilities.py` — capability `computer_use`, criticals, risk levels.
- Modify: `backend/app/tools/registry.py` ou ponto de registro de core tools (onde os tools nativos são instanciados).
- Modify: `backend/pyinstaller/*.spec` — hidden-imports comtypes/uiautomation.
- Modify: `backend/requirements.txt`.
- Test: `backend/tests/tools/test_computer_tools.py`, `backend/tests/tools/test_computer_native.py`.

**Fase C — loop + ativação**
- Modify: `backend/app/db/models.py` — `ConversationModel.computer_use_enabled`, `computer_use_display`.
- Create: `backend/alembic/versions/<rev>_computer_use_conversation_flags.py`.
- Modify: `backend/app/domain/schemas.py` — `ModelConfig.vision_provider_id/vision_model`; conversation schemas.
- Modify: `backend/app/runtime/agent_runtime.py` — injeção de imagem, roteamento de modelo de visão, política de contexto (só último screenshot).
- Modify: ponto onde a capability efetiva do run é montada (resolver onde `capabilities`→tools acontece).
- Modify: frontend — toggle por chat, seletor de display, campo de modelo de visão na config do agente, render de screenshot/ação.
- Test: `backend/tests/runtime/test_computer_use_loop.py`, `backend/tests/runtime/test_capability_gating.py`.

> Nota para o executor: alguns pontos de integração ("onde core tools são registrados", "onde capability→tools é montada", "onde o runtime constrói `ChatRequest`") exigem localizar a chamada exata antes de editar. Cada task abaixo começa com um passo de localização quando aplicável.

---

# FASE A — Pipeline de Visão

### Task A1: Schema de imagem em ChatMessage

**Files:**
- Modify: `backend/app/providers/schemas.py`
- Test: `backend/tests/providers/test_vision_payloads.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/providers/test_vision_payloads.py
from app.providers.schemas import ChatMessage, ImagePart, ModelInfo

def test_chatmessage_defaults_to_no_images():
    m = ChatMessage(role="user", content="oi")
    assert m.images == []

def test_chatmessage_accepts_images():
    m = ChatMessage(role="user", content="veja", images=[ImagePart(base64="QUJD")])
    assert m.images[0].base64 == "QUJD"
    assert m.images[0].media_type == "image/png"

def test_modelinfo_supports_vision_default_false():
    assert ModelInfo(id="x", name="x").supports_vision is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -v`
Expected: FAIL — `ImportError: cannot import name 'ImagePart'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/providers/schemas.py — adicionar perto de ChatMessage
class ImagePart(BaseModel):
    base64: str
    media_type: str = "image/png"

class ChatMessage(BaseModel):
    role: str
    content: str
    images: List[ImagePart] = Field(default_factory=list)
```
E em `ModelInfo` adicionar `supports_vision: bool = False`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/schemas.py backend/tests/providers/test_vision_payloads.py
git commit -m "feat(providers): add image parts to ChatMessage schema"
```

---

### Task A2: Ollama serializa imagens

**Files:**
- Modify: `backend/app/providers/ollama.py`
- Test: `backend/tests/providers/test_vision_payloads.py`

- [ ] **Step 1: Write the failing test**

```python
# adicionar em test_vision_payloads.py
from app.providers.ollama import _msg_to_ollama
from app.providers.schemas import ChatMessage, ImagePart

def test_ollama_text_only_is_unchanged():
    m = ChatMessage(role="user", content="oi")
    assert _msg_to_ollama(m) == {"role": "user", "content": "oi"}

def test_ollama_includes_images_base64_array():
    m = ChatMessage(role="user", content="veja", images=[ImagePart(base64="QUJD")])
    out = _msg_to_ollama(m)
    assert out["images"] == ["QUJD"]
    assert out["content"] == "veja"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -k ollama -v`
Expected: FAIL — `cannot import name '_msg_to_ollama'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/providers/ollama.py — função módulo-nível
def _msg_to_ollama(m) -> dict:
    out = {"role": m.role, "content": m.content}
    if getattr(m, "images", None):
        out["images"] = [img.base64 for img in m.images]
    return out
```
Substituir, em `chat` e `stream_chat`, o `[{"role": m.role, "content": m.content} for m in request.messages]` por `[_msg_to_ollama(m) for m in request.messages]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -k ollama -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/ollama.py backend/tests/providers/test_vision_payloads.py
git commit -m "feat(providers): ollama sends images in chat payload"
```

---

### Task A3: OpenRouter serializa imagens

**Files:**
- Modify: `backend/app/providers/openrouter.py`
- Test: `backend/tests/providers/test_vision_payloads.py`

- [ ] **Step 1: Write the failing test**

```python
from app.providers.openrouter import _msg_to_openrouter

def test_openrouter_text_only_is_string_content():
    m = ChatMessage(role="user", content="oi")
    assert _msg_to_openrouter(m) == {"role": "user", "content": "oi"}

def test_openrouter_images_become_content_parts():
    m = ChatMessage(role="user", content="veja", images=[ImagePart(base64="QUJD")])
    out = _msg_to_openrouter(m)
    assert out["content"][0] == {"type": "text", "text": "veja"}
    assert out["content"][1]["type"] == "image_url"
    assert out["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -k openrouter -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/providers/openrouter.py
def _msg_to_openrouter(m) -> dict:
    if not getattr(m, "images", None):
        return {"role": m.role, "content": m.content}
    parts = [{"type": "text", "text": m.content}]
    for img in m.images:
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{img.media_type};base64,{img.base64}"},
        })
    return {"role": m.role, "content": parts}
```
Localizar onde o openrouter monta `messages` no payload e usar `_msg_to_openrouter`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -k openrouter -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/openrouter.py backend/tests/providers/test_vision_payloads.py
git commit -m "feat(providers): openrouter sends images as content parts"
```

---

### Task A4: Detecção de supports_vision (allowlist Ollama)

**Files:**
- Modify: `backend/app/providers/ollama.py`
- Test: `backend/tests/providers/test_vision_payloads.py`

- [ ] **Step 1: Write the failing test**

```python
from app.providers.ollama import _model_supports_vision

def test_known_vision_families_detected():
    assert _model_supports_vision("llava:7b") is True
    assert _model_supports_vision("gemma3:4b") is True
    assert _model_supports_vision("qwen2.5vl:7b") is True

def test_text_model_not_vision():
    assert _model_supports_vision("llama3.1:8b") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -k vision_families -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/providers/ollama.py
_VISION_FAMILIES = ("llava", "gemma3", "qwen2.5vl", "qwen2.5-vl",
                    "llama3.2-vision", "minicpm-v", "moondream", "bakllava")

def _model_supports_vision(name: str) -> bool:
    n = name.lower()
    return any(fam in n for fam in _VISION_FAMILIES)
```
Em `list_models`, setar `supports_vision=_model_supports_vision(m["name"])` no `ModelInfo`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/providers/test_vision_payloads.py -v`
Expected: PASS (todos da fase A).

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/ollama.py backend/tests/providers/test_vision_payloads.py
git commit -m "feat(providers): detect vision-capable ollama models via allowlist"
```

---

# FASE B — Camada Nativa + Tools `screen.*`

### Task B1: Dependências e DPI awareness

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/tools/core/computer.py`
- Test: `backend/tests/tools/test_computer_native.py`

- [ ] **Step 1: Adicionar deps**

Em `backend/requirements.txt` acrescentar:
```
mss
pynput
uiautomation
```
(`Pillow` já deve existir; se não, adicionar.) Rodar `cd backend && pip install -r requirements.txt`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/tools/test_computer_native.py
from app.tools.core import computer

def test_remap_scales_model_coords_to_real_pixels():
    # imagem foi reduzida por 0.5 → coord do modelo (100,50) vira (200,100)
    assert computer.remap(100, 50, scale_x=0.5, scale_y=0.5) == (200, 100)

def test_parse_combo_splits_modifiers():
    assert computer.parse_combo("ctrl+c") == ["ctrl", "c"]
    assert computer.parse_combo("enter") == ["enter"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -v`
Expected: FAIL — module/func não existe.

- [ ] **Step 4: Write minimal implementation**

```python
# backend/app/tools/core/computer.py
import ctypes, sys

def _set_dpi_aware():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

_set_dpi_aware()

def remap(x: int, y: int, scale_x: float, scale_y: float) -> tuple[int, int]:
    return (round(x / scale_x), round(y / scale_y))

def parse_combo(combo: str) -> list[str]:
    return [k.strip().lower() for k in combo.split("+") if k.strip()]
```

- [ ] **Step 5: Run test + commit**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -v` → PASS.
```bash
git add backend/requirements.txt backend/app/tools/core/computer.py backend/tests/tools/test_computer_native.py
git commit -m "feat(computer): native module skeleton with DPI awareness + coord remap"
```

---

### Task B2: Captura com downscale e fator de escala

**Files:**
- Modify: `backend/app/tools/core/computer.py`
- Test: `backend/tests/tools/test_computer_native.py`

- [ ] **Step 1: Write the failing test**

```python
def test_compute_downscale_keeps_aspect_and_factor():
    # 3000x2000, limite 1568 → escala = 1568/3000
    w, h, sx, sy = computer.compute_downscale(3000, 2000, max_side=1568)
    assert w == 1568
    assert sx == sy
    assert round(sx, 4) == round(1568/3000, 4)

def test_compute_downscale_noop_when_small():
    assert computer.compute_downscale(800, 600, max_side=1568) == (800, 600, 1.0, 1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -k downscale -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
def compute_downscale(w: int, h: int, max_side: int = 1568):
    longest = max(w, h)
    if longest <= max_side:
        return (w, h, 1.0, 1.0)
    s = max_side / longest
    return (round(w * s), round(h * s), s, s)
```
E a função real de captura (não testada em unit, exercida em integração):
```python
def capture(display: int = 0, max_side: int = 1568):
    import io, mss
    from PIL import Image
    with mss.mss() as sct:
        mon = sct.monitors[display + 1]  # [0] é "all"; +1 = monitor físico
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    nw, nh, sx, sy = compute_downscale(img.width, img.height, max_side)
    if (nw, nh) != (img.width, img.height):
        img = img.resize((nw, nh))
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return {"png": buf.getvalue(), "scale_x": sx, "scale_y": sy,
            "real_w": mon["width"], "real_h": mon["height"],
            "origin_x": mon["left"], "origin_y": mon["top"]}
```

- [ ] **Step 4: Run test + commit**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -k downscale -v` → PASS.
```bash
git add backend/app/tools/core/computer.py backend/tests/tools/test_computer_native.py
git commit -m "feat(computer): screen capture with aspect-preserving downscale"
```

---

### Task B3: Enumeração UIA + anotação

**Files:**
- Modify: `backend/app/tools/core/computer.py`
- Test: `backend/tests/tools/test_computer_native.py`

- [ ] **Step 1: Write the failing test** (testa a seleção/filtragem, com elementos mockados — não chama UIA real)

```python
def test_filter_keeps_interactive_visible_and_caps_count():
    raw = [
        {"role": "Button", "name": "OK", "bbox": (0,0,50,20), "visible": True, "enabled": True, "area": 1000},
        {"role": "Text",   "name": "label", "bbox": (0,0,10,10), "visible": True, "enabled": True, "area": 100},
        {"role": "Button", "name": "Hidden", "bbox": (0,0,1,1), "visible": False, "enabled": True, "area": 1},
    ]
    out = computer.filter_elements(raw, max_count=80)
    roles = [e["role"] for e in out]
    assert "Text" not in roles          # não-interativo descartado
    assert "OK" in [e["name"] for e in out]
    assert all(e["visible"] for e in out)
    assert out[0]["id"] == 0            # ids sintéticos 0..N
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -k filter_elements -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
_INTERACTIVE = {"Button", "Edit", "CheckBox", "RadioButton", "ComboBox",
                "MenuItem", "ListItem", "Hyperlink", "TabItem", "Slider"}

def filter_elements(raw: list[dict], max_count: int = 80) -> list[dict]:
    kept = [e for e in raw if e.get("visible") and e.get("role") in _INTERACTIVE]
    kept.sort(key=lambda e: e.get("area", 0), reverse=True)
    kept = kept[:max_count]
    for i, e in enumerate(kept):
        e["id"] = i
    return kept

def enumerate_elements(display: int = 0, max_count: int = 80) -> list[dict]:
    # Implementação real com uiautomation: percorre a janela em foco,
    # coleta role/name/bbox/visible/enabled, depois filter_elements(...).
    import uiautomation as auto
    raw = []
    root = auto.GetForegroundControl()
    for ctrl, depth in _walk(root, max_depth=25):   # _walk helper abaixo
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
    return filter_elements(raw, max_count)

def _walk(ctrl, max_depth, depth=0):
    if ctrl is None or depth > max_depth:
        return
    yield ctrl, depth
    try:
        for child in ctrl.GetChildren():
            yield from _walk(child, max_depth, depth + 1)
    except Exception:
        return

def annotate(png: bytes, elements: list[dict], scale_x: float, scale_y: float) -> bytes:
    import io
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(png)).convert("RGB")
    d = ImageDraw.Draw(img)
    for e in elements:
        l, t, r, b = e["bbox"]
        box = (l*scale_x, t*scale_y, r*scale_x, b*scale_y)
        d.rectangle(box, outline=(255, 0, 0), width=2)
        d.text((box[0]+2, box[1]+2), str(e["id"]), fill=(255, 0, 0))
    out = io.BytesIO(); img.save(out, format="PNG")
    return out.getvalue()
```

- [ ] **Step 4: Run test + commit**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -k filter_elements -v` → PASS.
```bash
git add backend/app/tools/core/computer.py backend/tests/tools/test_computer_native.py
git commit -m "feat(computer): UIA element enumeration + set-of-marks annotation"
```

---

### Task B4: Atuação (mouse/teclado)

**Files:**
- Modify: `backend/app/tools/core/computer.py`
- Test: `backend/tests/tools/test_computer_native.py`

- [ ] **Step 1: Write the failing test** (com `pynput` mockado via monkeypatch)

```python
def test_press_keys_maps_combo(monkeypatch):
    pressed = []
    class FakeKb:
        def press(self, k): pressed.append(("press", k))
        def release(self, k): pressed.append(("release", k))
    monkeypatch.setattr(computer, "_keyboard", FakeKb())
    computer.press_keys("ctrl+a")
    assert ("press", "ctrl") in pressed and ("press", "a") in pressed
    # libera na ordem inversa
    assert pressed.index(("release", "a")) < pressed.index(("release", "ctrl"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -k press_keys -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# pynput inicializado lazy para não exigir display em import/CI
_mouse = None
_keyboard = None
def _kb():
    global _keyboard
    if _keyboard is None:
        from pynput.keyboard import Controller; _keyboard = Controller()
    return _keyboard
def _ms():
    global _mouse
    if _mouse is None:
        from pynput.mouse import Controller; _mouse = Controller()
    return _mouse

def press_keys(combo: str):
    kb = computer._keyboard or _kb()
    keys = parse_combo(combo)
    for k in keys: kb.press(_to_key(k))
    for k in reversed(keys): kb.release(_to_key(k))

def _to_key(name: str):
    from pynput.keyboard import Key
    return getattr(Key, name, name) if hasattr(Key, name) else name

def click(x, y, button="left", double=False):
    from pynput.mouse import Button
    ms = computer._mouse or _ms()
    ms.position = (x, y)
    ms.click(getattr(Button, button), 2 if double else 1)

def type_text(text: str):
    (computer._keyboard or _kb()).type(text)

def scroll(dx: int, dy: int):
    (computer._mouse or _ms()).scroll(dx, dy)
```
(O `monkeypatch` no teste seta `computer._keyboard`, por isso o código lê `computer._keyboard or _kb()`.)

- [ ] **Step 4: Run test + commit**

Run: `cd backend && python -m pytest tests/tools/test_computer_native.py -v` → PASS.
```bash
git add backend/app/tools/core/computer.py backend/tests/tools/test_computer_native.py
git commit -m "feat(computer): mouse/keyboard actuation via pynput"
```

---

### Task B5: Capability `computer_use` + criticals

**Files:**
- Modify: `backend/app/tools/capabilities.py`
- Test: `backend/tests/tools/test_computer_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/tools/test_computer_tools.py
from app.tools.capabilities import CAPABILITIES, CRITICAL_TOOLS, NATIVE_TOOLS

def test_computer_use_capability_registered():
    assert "screen.click" in CAPABILITIES["computer_use"]
    assert "screen.perceive" in CAPABILITIES["computer_use"]

def test_actuators_are_critical_perceive_is_not():
    assert "screen.click" in CRITICAL_TOOLS
    assert "screen.type" in CRITICAL_TOOLS
    assert "screen.key" in CRITICAL_TOOLS
    assert "screen.perceive" not in CRITICAL_TOOLS

def test_computer_use_never_native():
    assert not (NATIVE_TOOLS & set(CAPABILITIES["computer_use"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/tools/test_computer_tools.py -k capability -v`
Expected: FAIL — KeyError "computer_use".

- [ ] **Step 3: Write minimal implementation**

```python
# capabilities.py
CAPABILITIES["computer_use"] = [
    "screen.perceive", "screen.click", "screen.type", "screen.key", "screen.scroll",
]
CRITICAL_TOOLS = CRITICAL_TOOLS | frozenset({
    "screen.click", "screen.type", "screen.key", "screen.scroll",
})
# em TOOL_RISK_LEVELS marcar os 4 atuadores como "high".
```

- [ ] **Step 4: Run test + commit**

Run: `cd backend && python -m pytest tests/tools/test_computer_tools.py -k capability -v` → PASS.
```bash
git add backend/app/tools/capabilities.py backend/tests/tools/test_computer_tools.py
git commit -m "feat(tools): register computer_use capability and critical actuators"
```

---

### Task B6: Tools `screen.*` (BaseTool)

**Files:**
- Create: `backend/app/tools/core/computer_tools.py`
- Test: `backend/tests/tools/test_computer_tools.py`

- [ ] **Step 1: Write the failing test** (camada nativa mockada)

```python
import pytest
from app.tools.base import ToolExecutionContext
from app.tools.core import computer_tools

class FakeCtx(ToolExecutionContext):
    def __init__(self): self.extra = {}; self.execution_id="e"; self.agent_id="a"; self.workspace_ids=[]; self.db=None; self.approval_mode="auto"

@pytest.mark.asyncio
async def test_perceive_returns_elements_and_image(monkeypatch):
    monkeypatch.setattr(computer_tools.computer, "capture",
        lambda display=0: {"png": b"PNG", "scale_x":1.0,"scale_y":1.0,"real_w":100,"real_h":100,"origin_x":0,"origin_y":0})
    monkeypatch.setattr(computer_tools.computer, "enumerate_elements",
        lambda display=0, max_count=80: [{"id":0,"role":"Button","name":"OK","bbox":(0,0,50,20)}])
    monkeypatch.setattr(computer_tools.computer, "annotate", lambda *a, **k: b"ANNOTATED")
    ctx = FakeCtx()
    out = await computer_tools.ScreenPerceiveTool().execute({"display":0}, ctx)
    assert any(e["name"] == "OK" for e in out["elements"])
    assert "image_base64" in out
    assert ctx.extra["computer_use_last_map"][0]["bbox"] == (0,0,50,20)

@pytest.mark.asyncio
async def test_click_by_element_id_uses_center_real_pixels(monkeypatch):
    clicks = []
    monkeypatch.setattr(computer_tools.computer, "click", lambda x,y,button="left",double=False: clicks.append((x,y)))
    ctx = FakeCtx()
    ctx.extra["computer_use_last_map"] = {0: {"bbox": (10,10,30,50), "origin_x":0, "origin_y":0}}
    await computer_tools.ScreenClickTool().execute({"element_id":0}, ctx)
    assert clicks == [(20, 30)]  # centro do bbox

@pytest.mark.asyncio
async def test_click_invalid_element_id_errors():
    ctx = FakeCtx(); ctx.extra["computer_use_last_map"] = {}
    out = await computer_tools.ScreenClickTool().execute({"element_id": 9}, ctx)
    assert out.get("error")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/tools/test_computer_tools.py -k "perceive or click" -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/tools/core/computer_tools.py
import base64
from app.tools.base import BaseTool
from app.tools.core import computer

class ScreenPerceiveTool(BaseTool):
    name = "screen.perceive"; capability = "computer_use"; critical = False
    description = "Captura a tela e lista elementos clicáveis (UIA) com ids."
    input_schema = {"type":"object","properties":{"display":{"type":"integer","default":0},
                    "annotate":{"type":"boolean","default":True}}}
    async def execute(self, arguments, context):
        display = arguments.get("display", 0)
        cap = computer.capture(display=display)
        els = computer.enumerate_elements(display=display)
        png = cap["png"]
        if arguments.get("annotate", True):
            png = computer.annotate(png, els, cap["scale_x"], cap["scale_y"])
        context.extra["computer_use_last_map"] = {
            e["id"]: {"bbox": e["bbox"], "origin_x": cap["origin_x"], "origin_y": cap["origin_y"]}
            for e in els
        }
        context.extra["computer_use_scale"] = (cap["scale_x"], cap["scale_y"])
        return {
            "elements": [{"id": e["id"], "role": e["role"], "name": e["name"]} for e in els],
            "image_base64": base64.b64encode(png).decode(),
            "display": display,
        }

class ScreenClickTool(BaseTool):
    name = "screen.click"; capability = "computer_use"; critical = True
    description = "Clica num elemento (element_id) ou em coordenada (x,y)."
    input_schema = {"type":"object","properties":{"element_id":{"type":"integer"},
                    "x":{"type":"integer"},"y":{"type":"integer"},
                    "button":{"type":"string","default":"left"},"double":{"type":"boolean","default":False}}}
    async def execute(self, arguments, context):
        button = arguments.get("button","left"); double = arguments.get("double",False)
        m = context.extra.get("computer_use_last_map", {})
        if "element_id" in arguments and arguments["element_id"] is not None:
            el = m.get(arguments["element_id"])
            if not el:
                return {"error": f"element_id {arguments['element_id']} não existe no último perceive"}
            l,t,r,b = el["bbox"]
            x = el["origin_x"] + (l+r)//2; y = el["origin_y"] + (t+b)//2
        else:
            sx, sy = context.extra.get("computer_use_scale", (1.0,1.0))
            x, y = computer.remap(arguments["x"], arguments["y"], sx, sy)
        computer.click(x, y, button=button, double=double)
        return {"status":"ok","x":x,"y":y}

class ScreenTypeTool(BaseTool):
    name = "screen.type"; capability = "computer_use"; critical = True
    description = "Digita texto no foco atual."
    input_schema = {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}
    async def execute(self, arguments, context):
        computer.type_text(arguments["text"]); return {"status":"ok"}

class ScreenKeyTool(BaseTool):
    name = "screen.key"; capability = "computer_use"; critical = True
    description = "Envia um atalho de teclado, ex: ctrl+c, enter, alt+tab."
    input_schema = {"type":"object","properties":{"combo":{"type":"string"}},"required":["combo"]}
    async def execute(self, arguments, context):
        computer.press_keys(arguments["combo"]); return {"status":"ok"}

class ScreenScrollTool(BaseTool):
    name = "screen.scroll"; capability = "computer_use"; critical = True
    description = "Rola a tela. dx/dy ou direction(up|down)+amount."
    input_schema = {"type":"object","properties":{"dx":{"type":"integer","default":0},
                    "dy":{"type":"integer","default":0},"direction":{"type":"string"},"amount":{"type":"integer","default":3}}}
    async def execute(self, arguments, context):
        dx = arguments.get("dx",0); dy = arguments.get("dy",0)
        if arguments.get("direction") == "down": dy = -arguments.get("amount",3)
        if arguments.get("direction") == "up": dy = arguments.get("amount",3)
        computer.scroll(dx, dy); return {"status":"ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/tools/test_computer_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/core/computer_tools.py backend/tests/tools/test_computer_tools.py
git commit -m "feat(tools): screen.* perceive/click/type/key/scroll tools"
```

---

### Task B7: Registrar os tools no core

**Files:**
- Modify: ponto de registro de core tools (localizar onde `FilesystemReadTool` etc. são instanciados/registrados — provavelmente um `register_core_tools(registry)` ou similar em `tools/core/__init__.py` ou no startup).
- Test: `backend/tests/tools/test_computer_tools.py`

- [ ] **Step 1: Localizar o registro**

Run: `cd backend && grep -rn "registry.register(" app/ | head`. Identificar a função/loop que registra os core tools.

- [ ] **Step 2: Write the failing test**

```python
def test_screen_tools_in_registry():
    from app.tools.registry import ToolRegistry
    from app.tools.core import register_core_tools  # ajustar ao nome real
    reg = ToolRegistry(); register_core_tools(reg)
    for name in ["screen.perceive","screen.click","screen.type","screen.key","screen.scroll"]:
        assert reg.exists(name)
```

- [ ] **Step 3: Run / fail / implement**

Adicionar instâncias `ScreenPerceiveTool(), ScreenClickTool(), ...` à lista/loop de registro de core tools, seguindo exatamente o padrão dos tools existentes.

- [ ] **Step 4: Run + commit**

Run: `cd backend && python -m pytest tests/tools/test_computer_tools.py -k registry -v` → PASS.
```bash
git add -A && git commit -m "feat(tools): register screen.* tools as core tools"
```

---

### Task B8: PyInstaller hidden-imports

**Files:**
- Modify: `backend/pyinstaller/*.spec`

- [ ] **Step 1: Localizar o .spec**

Run: `cd backend && ls pyinstaller`. Abrir o `.spec` principal.

- [ ] **Step 2: Adicionar hidden imports / collect**

No `Analysis(...)`:
```python
from PyInstaller.utils.hooks import collect_submodules
hiddenimports += collect_submodules('comtypes') + collect_submodules('uiautomation')
hiddenimports += ['comtypes.gen']
```

- [ ] **Step 3: Build e verificar**

Run (conforme processo de build do projeto): empacotar o backend e iniciar o exe; chamar `screen.perceive` num app aberto e confirmar que retorna elementos (sem erro de `comtypes.gen`).
Expected: percepção funciona no binário, não só no venv.

- [ ] **Step 4: Commit**

```bash
git add backend/pyinstaller && git commit -m "build: bundle comtypes/uiautomation for computer-use in PyInstaller"
```

---

# FASE C — Loop Perceber→Agir + Ativação por Chat

### Task C1: Flags de computer-use na conversa (DB + migration)

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/<rev>_computer_use_conversation_flags.py`
- Modify: `backend/app/domain/schemas.py` (conversation create/update/read)
- Test: `backend/tests/runtime/test_capability_gating.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/runtime/test_capability_gating.py
from app.db.models import ConversationModel
def test_conversation_has_computer_use_flags():
    c = ConversationModel()
    assert hasattr(c, "computer_use_enabled")
    assert hasattr(c, "computer_use_display")
```

- [ ] **Step 2: Run / fail**

Run: `cd backend && python -m pytest tests/runtime/test_capability_gating.py -k flags -v` → FAIL.

- [ ] **Step 3: Implement**

```python
# db/models.py — em ConversationModel
computer_use_enabled = Column(Boolean, default=False)
computer_use_display = Column(Integer, default=0)
```
Migration Alembic (gerar com `alembic revision -m "computer_use conversation flags"` e preencher):
```python
def upgrade():
    op.add_column("conversations", sa.Column("computer_use_enabled", sa.Boolean(), server_default=sa.false()))
    op.add_column("conversations", sa.Column("computer_use_display", sa.Integer(), server_default="0"))
def downgrade():
    op.drop_column("conversations", "computer_use_display")
    op.drop_column("conversations", "computer_use_enabled")
```
Adicionar os campos nos schemas Pydantic de conversa (create/update/read) seguindo `max_steps`/`workspace_ids`.

- [ ] **Step 4: Run + migrate + commit**

Run: `cd backend && alembic upgrade head` então `python -m pytest tests/runtime/test_capability_gating.py -k flags -v` → PASS.
```bash
git add -A && git commit -m "feat(db): per-conversation computer_use flags + migration"
```

---

### Task C2: Gating da capability (flag × concessão)

**Files:**
- Modify: ponto onde a capability efetiva do run é resolvida (localizar — onde `agent.capabilities` vira o conjunto de tools, provavelmente no runtime/execution_engine).
- Test: `backend/tests/runtime/test_capability_gating.py`

- [ ] **Step 1: Localizar a resolução de capabilities**

Run: `cd backend && grep -rn "capabilities" app/runtime app/orchestrator | head`.

- [ ] **Step 2: Write the failing test**

```python
from app.runtime.capability_gate import resolve_computer_use  # criar este helper puro

def test_computer_use_requires_flag_and_grant():
    assert resolve_computer_use(agent_has=True, chat_enabled=True) is True
    assert resolve_computer_use(agent_has=True, chat_enabled=False) is False
    assert resolve_computer_use(agent_has=False, chat_enabled=True) is False
```

- [ ] **Step 3: Run / fail / implement**

```python
# backend/app/runtime/capability_gate.py
def resolve_computer_use(agent_has: bool, chat_enabled: bool) -> bool:
    return bool(agent_has and chat_enabled)
```
No ponto de montagem de tools do run: se `"computer_use"` está nas capabilities do agente **mas** `resolve_computer_use(...)` é False, remover os tools `screen.*` do conjunto exposto (não entram no prompt).

- [ ] **Step 4: Run + commit**

Run: `cd backend && python -m pytest tests/runtime/test_capability_gating.py -v` → PASS.
```bash
git add -A && git commit -m "feat(runtime): gate computer_use by chat flag + agent grant"
```

---

### Task C3: vision_config por agente

**Files:**
- Modify: `backend/app/domain/schemas.py` (`ModelConfig`)
- Test: `backend/tests/runtime/test_computer_use_loop.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/runtime/test_computer_use_loop.py
from app.domain.schemas import ModelConfig
from app.runtime.vision_routing import pick_vision_target

def test_vision_config_optional_defaults_none():
    mc = ModelConfig(provider_id="ollama", model="gemma3:4b")  # ajustar aos campos reais
    assert mc.vision_provider_id is None

def test_pick_vision_target_prefers_explicit():
    mc = ModelConfig(provider_id="ollama", model="llama3.1:8b",
                     vision_provider_id="ollama", vision_model="qwen2.5vl:7b")
    assert pick_vision_target(mc, main_supports_vision=False) == ("ollama","qwen2.5vl:7b")

def test_pick_vision_target_falls_back_to_main_when_multimodal():
    mc = ModelConfig(provider_id="ollama", model="gemma3:4b")
    assert pick_vision_target(mc, main_supports_vision=True) == ("ollama","gemma3:4b")

def test_pick_vision_target_returns_none_when_no_vision():
    mc = ModelConfig(provider_id="ollama", model="llama3.1:8b")
    assert pick_vision_target(mc, main_supports_vision=False) is None
```

- [ ] **Step 2: Run / fail**

Run: `cd backend && python -m pytest tests/runtime/test_computer_use_loop.py -k vision -v` → FAIL.

- [ ] **Step 3: Implement**

```python
# domain/schemas.py — em ModelConfig
vision_provider_id: Optional[str] = None
vision_model: Optional[str] = None
```
```python
# backend/app/runtime/vision_routing.py
def pick_vision_target(mc, main_supports_vision: bool):
    if mc.vision_provider_id and mc.vision_model:
        return (mc.vision_provider_id, mc.vision_model)
    if main_supports_vision:
        return (mc.provider_id, mc.model)   # ajustar nomes reais dos campos
    return None
```

- [ ] **Step 4: Run + commit**

Run: `cd backend && python -m pytest tests/runtime/test_computer_use_loop.py -k vision -v` → PASS.
```bash
git add -A && git commit -m "feat(agent): per-agent vision model config + routing"
```

---

### Task C4: Injeção de imagem + política de só-último-screenshot

**Files:**
- Modify: `backend/app/runtime/agent_runtime.py`
- Test: `backend/tests/runtime/test_computer_use_loop.py`

- [ ] **Step 1: Write the failing test** (função pura de montagem das mensagens)

```python
from app.runtime.agent_runtime import build_messages_with_vision

def test_only_last_screenshot_kept():
    history = [
        {"role":"user","content":"faça login"},
        {"role":"assistant","content":"perceive", "screenshot_b64":"IMG1"},
        {"role":"assistant","content":"perceive", "screenshot_b64":"IMG2"},
    ]
    msgs = build_messages_with_vision(history)
    imgs = [m for m in msgs if m.images]
    assert len(imgs) == 1
    assert imgs[0].images[0].base64 == "IMG2"
```

- [ ] **Step 2: Run / fail**

Run: `cd backend && python -m pytest tests/runtime/test_computer_use_loop.py -k screenshot -v` → FAIL.

- [ ] **Step 3: Implement**

```python
# agent_runtime.py
from app.providers import ChatMessage
from app.providers.schemas import ImagePart

def build_messages_with_vision(history: list[dict]) -> list:
    last_img_idx = max((i for i,m in enumerate(history) if m.get("screenshot_b64")), default=None)
    msgs = []
    for i, m in enumerate(history):
        images = []
        if i == last_img_idx and m.get("screenshot_b64"):
            images = [ImagePart(base64=m["screenshot_b64"])]
        msgs.append(ChatMessage(role=m["role"], content=m["content"], images=images))
    return msgs
```
Integrar: onde o runtime hoje monta `messages=[ChatMessage(role=m["role"], content=m["content"]) for m in messages]` (no `ChatRequest`), usar `build_messages_with_vision(messages)` quando o run é computer-use. O resultado de `screen.perceive` deve gravar `screenshot_b64` na entrada de histórico daquele passo.

- [ ] **Step 4: Run + commit**

Run: `cd backend && python -m pytest tests/runtime/test_computer_use_loop.py -k screenshot -v` → PASS.
```bash
git add -A && git commit -m "feat(runtime): inject latest screenshot into model turn, drop older"
```

---

### Task C5: Roteamento do modelo de visão no turno

**Files:**
- Modify: `backend/app/runtime/agent_runtime.py`
- Test: `backend/tests/runtime/test_computer_use_loop.py`

- [ ] **Step 1: Write the failing test**

```python
from app.runtime.agent_runtime import choose_request_target

def test_turn_with_image_uses_vision_target():
    target = choose_request_target(has_image=True, main=("ollama","llama3.1"),
                                   vision=("ollama","qwen2.5vl:7b"))
    assert target == ("ollama","qwen2.5vl:7b")

def test_turn_without_image_uses_main():
    target = choose_request_target(has_image=False, main=("ollama","llama3.1"),
                                   vision=("ollama","qwen2.5vl:7b"))
    assert target == ("ollama","llama3.1")
```

- [ ] **Step 2: Run / fail / implement**

```python
def choose_request_target(has_image: bool, main: tuple, vision):
    if has_image and vision:
        return vision
    return main
```
Integrar no ponto de construção do `ChatRequest`: se o turno tem imagem e `pick_vision_target` retornou alvo, usar esse `provider_id`/`model`; senão o principal. Se `has_image` e `vision is None`, **não** anexar imagem (degradação: manda só o texto da UIA) e emitir evento `computer_use_no_vision_model`.

- [ ] **Step 3: Run + commit**

Run: `cd backend && python -m pytest tests/runtime/test_computer_use_loop.py -k turn -v` → PASS.
```bash
git add -A && git commit -m "feat(runtime): route vision turns to per-agent vision model"
```

---

### Task C6: Loop perceber→agir + cancelamento

**Files:**
- Modify: `backend/app/runtime/agent_runtime.py` (integra no ciclo de tools existente)
- Test: `backend/tests/runtime/test_computer_use_loop.py`

- [ ] **Step 1: Write the failing test** (loop com camada nativa e provider mockados)

```python
@pytest.mark.asyncio
async def test_loop_perceives_then_acts_then_stops(monkeypatch):
    # provider decide: 1º turno chama screen.perceive; 2º turno chama screen.click; 3º conclui.
    # asserta que houve >=1 perceive antes do 1º click e que respeita max_steps.
    ...
```
(Escrever asserts concretos contra um provider fake que devolve sequência fixa de tool-calls; validar ordem perceive→click e parada por conclusão.)

- [ ] **Step 2: Run / fail / implement**

Estender o ciclo de tool existente: o resultado de `screen.perceive` vira entrada de histórico com `screenshot_b64`; o próximo turno usa visão; `screen.click/type/key/scroll` passam pelo `_execute_tool_call` (approval flow já trata critical/auto-approve). Respeitar `max_steps` (já existe) e o cancel compartilhado do chat lifecycle (verificar a flag de cancel a cada iteração antes de `perceive`/ação).

- [ ] **Step 3: Run + commit**

Run: `cd backend && python -m pytest tests/runtime/test_computer_use_loop.py -v` → PASS.
```bash
git add -A && git commit -m "feat(runtime): perceive→act loop with cancel + step budget"
```

---

### Task C7: Frontend — toggle por chat + seletor de display

**Files:**
- Modify: frontend (componente da conversa onde ficam workspaces/auto-approve; localizar via grep por "auto_approve"/"workspace" no `apps/frontend/src`).
- Test: teste de componente conforme padrão do frontend (Vitest/RTL se existente).

- [ ] **Step 1: Localizar o painel da conversa**

Run: `grep -rn "auto" apps/frontend/src | grep -i approv | head` e localizar o controle de configuração do chat.

- [ ] **Step 2: Implement**

- Toggle "Computer Use" que persiste `computer_use_enabled` na conversa (API de update já existente para `max_steps`/`workspace_ids`).
- Seletor de display quando `computer_use_enabled`.
- Estado desabilitado + tooltip quando o agente-alvo não tem a capability `computer_use`.

- [ ] **Step 3: Verificar via preview**

Usar o workflow de preview do projeto: ligar o toggle, recarregar, confirmar persistência (GET da conversa traz `computer_use_enabled=true`).

- [ ] **Step 4: Commit**

```bash
git add apps/frontend && git commit -m "feat(frontend): per-chat computer-use toggle + display picker"
```

---

### Task C8: Frontend — campo de modelo de visão na config do agente

**Files:**
- Modify: frontend (tela de config do agente, onde está o seletor de modelo de texto).

- [ ] **Step 1: Implement**

Adicionar campo opcional "Modelo de visão" (provider+model), gravando em `model_config.vision_provider_id/vision_model`. Reusar o componente de seleção de modelo já usado para o modelo de texto.

- [ ] **Step 2: Verificar via preview**

Salvar um agente com modelo de visão, reabrir, confirmar persistência.

- [ ] **Step 3: Commit**

```bash
git add apps/frontend && git commit -m "feat(frontend): per-agent vision model selector"
```

---

### Task C9: Frontend — render de screenshot + ação no chat

**Files:**
- Modify: frontend (render de eventos/segments inline, onde tools inline já aparecem).

- [ ] **Step 1: Implement**

- Renderizar o evento de `screen.perceive` como miniatura do screenshot (clicável → ampliar).
- Renderizar cada ação ("clicou em «Entrar»", "digitou …").
- Indicador "computer use ativo" enquanto o loop roda.

Reusar o padrão de segments/inline tools já existente (memória: inline tools via segments em groupEvents).

- [ ] **Step 2: Verificar via preview**

Rodar uma tarefa curta de computer-use e confirmar que screenshots e ações aparecem inline e o botão Parar interrompe.

- [ ] **Step 3: Commit**

```bash
git add apps/frontend && git commit -m "feat(frontend): render computer-use screenshots and actions inline"
```

---

### Task C10: E2E manual + ajustes

- [ ] **Step 1:** Ativar computer-use num chat, agente com capability + modelo de visão, **auto-approve ON**: pedir "abra o Bloco de Notas e escreva 'olá'". Confirmar perceber→agir completo.
- [ ] **Step 2:** Repetir com **auto-approve OFF**: confirmar que cada ação crítica pausa pedindo aprovação.
- [ ] **Step 3:** Testar o botão **Parar** no meio do loop.
- [ ] **Step 4:** Teste com display em escala 150%.
- [ ] **Step 5:** Rodar no **binário empacotado** (não só venv).
- [ ] **Step 6:** Commit de quaisquer ajustes + atualizar memória do projeto.

---

## Self-Review (resultado)

- **Cobertura do spec:** A (A1–A4 = schema+ollama+openrouter+detecção). B (B1–B8 = deps/DPI, captura, UIA/anotação, atuação, capability, tools, registro, PyInstaller). C (C1–C10 = flags+migration, gating, vision_config, injeção imagem, roteamento, loop, 3× frontend, E2E). Cada seção dos specs 09/10/11 tem task correspondente.
- **Placeholders:** loop C6 e teste E2E descrevem asserts a completar pelo executor (dependem de pontos de integração a localizar) — sinalizados explicitamente, não são código a copiar cego.
- **Consistência de tipos:** `computer.capture/enumerate_elements/annotate/click/type_text/press_keys/scroll/remap/parse_combo`, `context.extra["computer_use_last_map"]`, `ImagePart.base64`, `pick_vision_target`, `choose_request_target`, `resolve_computer_use`, `build_messages_with_vision` — nomes usados de forma consistente entre tasks.
- **Pontos a localizar (não placeholders de design, e sim de navegação no código):** registro de core tools (B7), resolução de capabilities→tools (C2), construção do `ChatRequest` no runtime (C4/C5/C6), painel de conversa e config de agente no frontend (C7–C9). Cada um tem passo de `grep` inicial.
