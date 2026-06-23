# 08-computer-use-overview.md

# AgentDesk — Computer Use (Visão + Controle de Tela) — Overview

> Data: 2026-06-22
> Status: Spec aprovado (desenho). Decomposto em 3 fases sequenciais.
> Specs relacionados: [09-computer-use-vision-pipeline.md](09-computer-use-vision-pipeline.md), [10-computer-use-perception-tools.md](10-computer-use-perception-tools.md), [11-computer-use-loop-activation.md](11-computer-use-loop-activation.md)

## 1. Objetivo

Permitir que um agente do AgentDesk **veja a tela do próprio PC do usuário e interaja com ela como um humano** — tirar screenshots, ler a UI, mover o mouse, clicar, digitar texto e enviar atalhos de teclado.

O caso de uso central é executar tarefas em **qualquer aplicativo desktop ou site**, sem depender de ferramentas de browser baseadas em DOM (que o usuário considera frágeis). O agente opera no nível de pixels + acessibilidade, igual uma pessoa faria.

Premissas aceitas pelo usuário: latência e custo de tokens existem e são tolerados, mitigados por **modelos de visão locais** (via Ollama) configuráveis por agente.

## 2. Princípio de design: grounding híbrido (UIA-first + visão)

O problema mais difícil de computer-use **não é** capturar tela nem clicar — é o *grounding*: dado o que está na tela, decidir a coordenada `(x, y)` certa. Modelos locais pequenos (ex.: gemma3 4B) erram coordenadas com frequência.

A solução adotada é **híbrida**:

1. **UIA-first (Windows UI Automation):** o backend enumera os elementos da UI via árvore de acessibilidade do Windows. Cada elemento vem com rótulo, tipo e *bounding box* exato. O agente clica escolhendo um **elemento por id** (`screen.click(element_id=7)`), não adivinhando pixels — confiável até com modelos fracos.
2. **Visão como fallback/reforço:** quando a UIA não expõe nada útil (canvas, jogos, apps que se desenham sozinhos, conteúdo dentro de browser que não publica accessibility), o agente cai para **coordenadas visuais** (`screen.click(x, y)`) a partir do screenshot anotado.

Isso muda o veredito de "frustrante" para "utilizável".

## 3. Decisões transversais (valem para as 3 fases)

| Tema | Decisão |
|------|---------|
| **Grounding** | Híbrido: UIA-first + fallback visual (seção 2). |
| **Controle/segurança** | Os tools de atuação são `critical=True` e passam pelo **approval flow existente**. Auto-approve ligado → agente autônomo; desligado → pausa pedindo confirmação em cada ação crítica. **Nenhum plano de controle novo.** |
| **Kill switch** | O botão **Parar** do chat (já existente) cancela o turno em andamento. |
| **Modelo de visão** | **Por agente**, igual o modelo de texto já é. Novo campo `vision_config` (opcional) no `model_config` do agente. Cai para o modelo principal se o provider já for multimodal e `vision_config` estiver vazio. |
| **Ativação** | **Por chat** (explícito). Flag `computer_use_enabled` na conversa, espelhando o padrão de `workspace_ids` / `max_steps` que já existe em `ConversationModel`. Capability `computer_use` só é liberada para o run se a flag estiver ligada **e** o agente tiver a capability concedida. |
| **perceive vs. act** | Separados: `screen.perceive` (olhar) e tools de atuação (`screen.click/type/key/scroll`). |
| **Plataforma** | **Windows-only** no MVP (UIA + DPI). Abstração de backend deixa porta aberta para macOS/Linux depois, fora de escopo. |

## 4. Arquitetura de alto nível

```txt
┌──────────────────────────────────────────────────────────────┐
│ Frontend (chat)                                              │
│  - Toggle "Computer Use" por conversa  ──────────┐          │
│  - Render de screenshots/ações via event bus      │          │
└───────────────────────────────────────────────────┼──────────┘
                                                     │
┌────────────────────────────────────────────────────▼─────────┐
│ Backend (Python / FastAPI)                                    │
│                                                               │
│  ConversationModel.computer_use_enabled ── libera capability  │
│                                                               │
│  Runtime (perceive→act loop)                                  │
│    1. screen.perceive  ──►  PerceptionResult                  │
│         (screenshot anotado + lista de elementos UIA)         │
│    2. injeta no turno (texto UIA + imagem) ──► Provider       │
│    3. modelo decide ação                                      │
│    4. screen.click/type/key/scroll  (CRITICAL → approval)     │
│    5. volta ao passo 1 até concluir / max_steps               │
│                                                               │
│  Camada de percepção/atuação (novo módulo computer.py)        │
│    - mss / Pillow           → screenshot                      │
│    - uiautomation/pywinauto → árvore UIA + bounding boxes     │
│    - pynput / pyautogui      → mouse + teclado                │
│                                                               │
│  Providers (Ollama / OpenRouter) — agora aceitam imagens      │
└───────────────────────────────────────────────────────────────┘
```

## 5. Decomposição em fases

Cada fase é testável isoladamente e tem seu próprio spec.

### Fase A — Pipeline de visão (`09-computer-use-vision-pipeline.md`)
Fazer imagens chegarem ao modelo. Hoje `ChatMessage.content` é `str` puro e os providers só mandam texto. É o trabalho net-new "invisível" mas necessário para tudo o mais. **Pré-requisito das fases B e C.**

### Fase B — Tools de computer-use + percepção UIA (`10-computer-use-perception-tools.md`)
A capability `computer_use`, o módulo de captura/atuação, a percepção híbrida (UIA + screenshot anotado) e os tools `screen.*`. Depende de A para o `screen.perceive` devolver imagem ao modelo.

### Fase C — Loop perceber→agir + ativação por chat (`11-computer-use-loop-activation.md`)
O loop de percepção→ação no runtime, a flag de ativação por conversa, o toggle no frontend e o `vision_config` por agente. Amarra A e B numa experiência de ponta a ponta.

## 6. Riscos conhecidos

- **Empacotamento PyInstaller** de `uiautomation`/`comtypes`/`pywinauto`: exige `hidden-imports` e possivelmente `collect-all`. Conhecido e resolvível, mas demanda teste no build empacotado, não só no `venv`.
- **DPI scaling do Windows**: coordenadas precisam ser normalizadas por display (process DPI-aware), senão os cliques caem deslocados. Tratado na Fase B.
- **Precisão de modelos locais pequenos** no fallback visual puro: mitigado pelo UIA-first; documentar que tarefas em apps sem accessibility funcionam melhor com modelos de visão mais fortes (configuráveis por agente).
- **Segurança**: o agente controla mouse/teclado reais. Mitigado por: ativação explícita por chat, approval em ações críticas quando auto-approve está off, e o botão Parar.

## 7. Fora de escopo (YAGNI)

- macOS / Linux.
- Gravação/replay de macros.
- OCR dedicado (a UIA já entrega texto; OCR só se virar necessidade real).
- Controle de múltiplas máquinas / remoto.
- Modelo de visão "set-of-marks" puro sem UIA (preterido em favor do híbrido).
