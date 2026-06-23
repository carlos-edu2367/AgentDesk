# 11-computer-use-loop-activation.md

# AgentDesk — Fase C: Loop Perceber→Agir + Ativação por Chat

> Parte de [08-computer-use-overview.md](08-computer-use-overview.md). Depende das fases A ([09](09-computer-use-vision-pipeline.md)) e B ([10](10-computer-use-perception-tools.md)).

## 1. Objetivo

Amarrar visão (A) e tools (B) numa experiência ponta a ponta: o loop perceber→agir no runtime, a ativação explícita por conversa, o modelo de visão configurável por agente e o render no chat.

## 2. Ativação por chat

### 2.1 Modelo de dados
`ConversationModel` (`backend/app/db/models.py`) ganha:
```python
computer_use_enabled = Column(Boolean, default=False)
computer_use_display = Column(Integer, default=0)  # qual monitor
```
Espelha exatamente o padrão de `workspace_ids` / `max_steps` já existentes na conversa. Migration Alembic correspondente.

### 2.2 Liberação da capability
No início do run, a capability `computer_use` só entra no conjunto efetivo de tools se **ambos**:
- a conversa tem `computer_use_enabled = True`; **e**
- o agente tem `computer_use` em `capabilities` (concessão explícita).

Caso contrário, os tools `screen.*` não são expostos ao modelo (nem aparecem no prompt). Essa é a checagem final de segurança mencionada na fase B.

### 2.3 Frontend
- Toggle **"Computer Use"** na conversa (perto do seletor de workspaces/auto-approve já existente).
- Quando ligado e o agente não tem a capability concedida: avisar o usuário (estado desabilitado + tooltip explicando que o agente precisa da capability).
- Seletor opcional de display quando há múltiplos monitores.

## 3. Modelo de visão por agente

`ModelConfig` (no `model_config` do agente) ganha um sub-config opcional:
```python
class ModelConfig(BaseModel):
    # ...campos atuais...
    vision_provider_id: Optional[str] = None
    vision_model: Optional[str] = None
```
- Se vazio **e** o modelo principal suporta visão (`supports_vision`, fase A) → usa o principal.
- Se vazio e o principal **não** suporta visão → o turno de percepção usa o modelo principal só com o **texto da UIA** (degradação graciosa, sem imagem) e registra um evento avisando que não há modelo de visão configurado.
- Se preenchido → o turno que consome o screenshot roteia para esse provider/modelo.

UI: campo de modelo de visão na config do agente, ao lado do modelo de texto (reusa o componente de seleção de provider/modelo existente).

## 4. Loop perceber→agir (runtime)

No `agent_runtime.py`, o ciclo de tool atual é "chama tool → injeta resultado textual → repete". Para computer-use, o resultado de `screen.perceive` precisa virar **imagem + texto** no próximo turno do modelo.

### 4.1 Fluxo
```
loop (até concluir ou max_steps):
  1. (se necessário) screen.perceive  → PerceptionResult {texto UIA, imagem PNG}
  2. monta ChatMessage do "observador": content = texto UIA,
     images = [ImagePart(base64=screenshot)]   ← usa pipeline da fase A
  3. modelo decide próxima ação (escolhe element_id ou x,y, ou texto/atalho)
  4. screen.click/type/key/scroll  (CRITICAL → approval flow; auto-approve respeitado)
  5. emite eventos (screenshot, ação) no event bus
  6. repete
```

### 4.2 Pontos de integração
- A injeção de imagem reusa o `ChatMessage.images` da fase A no ponto onde o runtime monta `messages=[ChatMessage(...)]` (hoje em `agent_runtime.py`, na construção do `ChatRequest`).
- Roteamento do modelo de visão: quando a mensagem do turno carrega imagem, usar `vision_provider_id/vision_model` se definidos (seção 3).
- `max_steps` por conversa (já existe) limita o loop. Sem isso, computer-use pode rodar indefinidamente.
- Cancelamento: o botão **Parar** já cancela o turno; garantir que um `perceive`/ação em andamento respeite o cancel compartilhado (mesma infra do chat lifecycle).

### 4.3 Gestão de contexto
Screenshots são pesados em tokens/imagem. Estratégia:
- Manter no contexto do modelo **apenas o último** screenshot/percepção (descartar imagens de passos anteriores, preservando um resumo textual das ações já tomadas).
- Reusa/estende a compactação de tool-result que já existe (`_compact_tool_result_for_model`).

## 5. Render no chat (frontend)

- Cada passo do loop emite eventos já suportados pelo padrão de segments/inline tools: mostrar a miniatura do screenshot (clicável para ampliar) e a ação tomada ("clicou em «Entrar»", "digitou …").
- Indicador de "computer use ativo" no chat enquanto o loop roda.

## 6. Segurança (consolidação)

- Ativação explícita por chat (seção 2) — desligado por padrão.
- Atuadores críticos → approval flow; auto-approve off ⇒ confirma cada ação crítica.
- Botão Parar = kill switch.
- Indicação visual clara de que o agente está controlando a máquina.

## 7. Critérios de aceite

1. Toggle por chat liga/desliga a exposição dos tools `screen.*` ao modelo (verificável no prompt/tools do run).
2. Com a flag desligada, agente **não** consegue controlar a tela mesmo tendo a capability.
3. Tarefa ponta a ponta (ex.: "abra o site X e faça login com estas credenciais") completa via perceber→agir, com screenshots e ações aparecendo no chat.
4. Com auto-approve off, cada ação crítica pausa pedindo confirmação; o botão Parar interrompe na hora.
5. Modelo de visão por agente é respeitado; agente sem modelo de visão degrada para texto-UIA com aviso.
6. Apenas o último screenshot permanece no contexto (sem inchaço linear de tokens).

## 8. Testes

- Unit: liberação da capability (matriz flag × capability concedida).
- Unit: roteamento de modelo de visão (principal multimodal / vision_config / degradação).
- Unit: política de contexto mantém só o último screenshot.
- Integração: loop completo com camada nativa e provider mockados (perceive→decisão→click→perceive).
- Manual (E2E): tarefa real de login em site, com auto-approve on e off, e teste do botão Parar no meio.
