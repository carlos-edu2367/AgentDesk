# 10-computer-use-perception-tools.md

# AgentDesk — Fase B: Tools de Computer Use + Percepção UIA

> Parte de [08-computer-use-overview.md](08-computer-use-overview.md). Depende da Fase A ([09](09-computer-use-vision-pipeline.md)) para o `screen.perceive` entregar imagem ao modelo.

## 1. Objetivo

Criar a capability `computer_use`, a camada nativa de captura/atuação no Windows e os tools `screen.*` que o agente usa para olhar a tela e interagir com ela.

## 2. Dependências de runtime (Python)

Adicionar a `backend/requirements.txt`:

- `mss` — screenshot rápido e multi-monitor.
- `Pillow` — manipulação/anotação/encode da imagem (provavelmente já presente).
- `pynput` — mouse e teclado.
- `uiautomation` — árvore UI Automation do Windows (wrapper sobre comtypes).

`pyautogui` é alternativa a `pynput`; escolher **`pynput`** (mais leve, sem dependência de tkinter). `pywinauto` é alternativa a `uiautomation`; escolher **`uiautomation`** (API direta a UIA, menos overhead).

## 3. Camada nativa — `backend/app/tools/core/computer.py`

Módulo isolado, sem dependência do resto das tools, testável com mocks. Responsabilidades:

### 3.1 DPI awareness
No import do módulo (uma vez), marcar o processo como **Per-Monitor DPI Aware** (`ctypes.windll.shcore.SetProcessDpiAwareness(2)` com fallback). Sem isso, as coordenadas da UIA/screenshot não batem com o mouse real em telas com escala ≠ 100%.

### 3.2 Captura
```python
def capture(display: int = 0) -> CaptureResult:
    """Screenshot do display. Retorna PNG bytes + (width, height) reais + escala."""
```
- Downscale para lado maior ≤ 1568px **mantendo o fator de escala** (`scale_x`, `scale_y`) para remapear coordenadas do modelo → pixels reais.
- Multi-monitor: `display` seleciona o monitor (o usuário tem múltiplos displays).

### 3.3 Percepção UIA
```python
def enumerate_elements(display: int = 0) -> list[UIElement]:
    """Elementos interativos visíveis: id sintético, role, name/label,
    bounding box (em pixels reais), enabled/focusable."""
```
- Filtrar para elementos **interativos e visíveis** (Button, Edit, CheckBox, MenuItem, ListItem, Hyperlink, etc.) dentro da janela em foco / monitor alvo, com limite de profundidade e de quantidade (ex.: top 80 por área/relevância) para não estourar o contexto do modelo.
- `id` sintético estável dentro de um `perceive` (índice 0..N), referenciado por `screen.click(element_id=...)`.

### 3.4 Anotação
```python
def annotate(png: bytes, elements: list[UIElement]) -> bytes:
    """Desenha caixas + número do id sobre o screenshot (set-of-marks)."""
```
Ajuda o modelo a correlacionar a lista textual de elementos com a imagem.

### 3.5 Atuação
```python
def click(x, y, button="left", double=False) -> None
def move(x, y) -> None
def type_text(text: str) -> None
def press_keys(combo: str) -> None     # ex.: "ctrl+c", "enter", "alt+tab"
def scroll(dx: int, dy: int) -> None
```
- Todas operam em **pixels reais**; o remapeamento de coordenadas do modelo (imagem downscaled) → reais acontece **no tool**, não na camada nativa.

## 4. Capability e registro

`backend/app/tools/capabilities.py`:

```python
CAPABILITIES["computer_use"] = [
    "screen.perceive",
    "screen.click",
    "screen.type",
    "screen.key",
    "screen.scroll",
]
```

- Adicionar `screen.click`, `screen.type`, `screen.key`, `screen.scroll` a `CRITICAL_TOOLS` (passam pelo approval flow).
- `screen.perceive` **não** é critical (só lê) — mas só existe se a capability estiver concedida.
- `TOOL_RISK_LEVELS`: marcar os atuadores como risco alto.
- **Não** adicionar a `NATIVE_TOOLS` (nunca é default; sempre exige concessão explícita + ativação por chat — fase C).

## 5. Tools (`screen.*`) — `BaseTool`

Seguem o padrão de `BaseTool` (name, description, capability="computer_use", critical, input/output schema, `execute`).

### 5.1 `screen.perceive`
- Input: `{ "display": int = 0, "annotate": bool = true }`
- Execute: `capture()` + `enumerate_elements()` (+ `annotate()`), guarda o mapa `element_id → bbox` no `context.extra` (estado do passo) para os tools de clique resolverem ids.
- Output: lista textual de elementos (`id, role, label`) **e** a imagem anotada. A imagem é devolvida de forma que o runtime (fase C) a injete como `ChatMessage.images`.

### 5.2 `screen.click`
- Input: `{ "element_id": int }` **ou** `{ "x": int, "y": int }`, `button`, `double`.
- `element_id` resolve via o mapa do último `perceive`; senão usa `x,y` (fallback visual).
- Erro claro se `element_id` não existe no último perceive.

### 5.3 `screen.type` / `screen.key` / `screen.scroll`
- `type`: `{ "text": str }`. `key`: `{ "combo": str }`. `scroll`: `{ "dx": int, "dy": int }` ou `{ "direction": "up|down", "amount": int }`.

## 6. Segurança nesta fase

- Tools de atuação são `critical=True` ⇒ approval flow existente cuida do gating (fase C amarra com a flag de ativação por chat).
- Sem ativação por chat (fase C), a capability `computer_use`, mesmo concedida ao agente, **não** deve produzir efeito — garantir que B não habilita atuação sozinha (a checagem final fica em C; B é a mecânica).

## 7. Empacotamento (PyInstaller)

- `uiautomation`/`comtypes` precisam de `hidden-imports` (`comtypes.gen.*`) e possivelmente `collect-submodules`. Atualizar o spec do PyInstaller em `backend/pyinstaller/`.
- Validar **no executável empacotado**, não só no venv — `comtypes.gen` é gerado em runtime e quebra fácil em build congelado.

## 8. Critérios de aceite

1. `screen.perceive` retorna ≥1 elemento clicável de uma janela conhecida (ex.: Bloco de Notas aberto) com bbox plausível.
2. `screen.click(element_id=...)` clica no elemento correto (validável abrindo menu/botão e conferindo efeito).
3. Coordenadas corretas em display com escala 125%/150% (teste DPI).
4. `screen.type` digita no campo focado; `screen.key("ctrl+a")` seleciona.
5. Tools aparecem no registry sob capability `computer_use` e como críticos.
6. Funciona no binário PyInstaller empacotado.

## 9. Testes

- Unit: camada nativa com UIA/pynput mockados (resolução de coordenadas, downscale↔remapeamento, parse de `combo`).
- Unit: `screen.click` resolve `element_id` e cai para `x,y`; erro quando id inválido.
- Manual/integração: roteiro no Bloco de Notas e numa página aberta no navegador (abrir menu, digitar, atalho), incluindo um display com escala ≠ 100%.
