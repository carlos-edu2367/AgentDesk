# Implementation Plan — AgentDesk

## 1. Contexto

O AgentDesk é um sistema desktop multiagêntico, open-source, Windows-first, criado para permitir que usuários configurem e executem agentes de IA para tarefas do dia a dia, automações locais, organização de informações, gerenciamento de arquivos, pesquisa, criação de documentos e, opcionalmente, desenvolvimento de código.

O sistema deve funcionar como uma plataforma local de agentes configuráveis, com suporte a:

* Modelos locais via Ollama.
* Modelos remotos via OpenRouter.
* Modelo diferente por agente.
* Agentes com system prompt, tools, skills, memória e permissões próprias.
* Agentes capazes de chamar subagentes.
* Times de agentes com agente chefe.
* Execuções com timeline visível.
* Modo manual com aprovação.
* Modo auto-approval 100% automático, sem confirmação durante a execução.
* Workspaces configuráveis pelo usuário.
* Tools nativas, tools de plugins e tools MCP.
* Memória global, por agente, por time e futuramente por workspace.
* Embeddings locais via Ollama.
* Skills locais baseadas em prompt/template.
* Plugins locais baseados em manifesto e scripts.
* Servidores MCP configuráveis manualmente.
* Auditoria completa de execuções e ações.

O MVP será grande, mas deve ser implementado como um conjunto modular e incremental, evitando dependências circulares e evitando que o frontend ou o modelo tenham acesso direto às ações críticas do sistema.

---

## 2. Specs consideradas

O plano considera o pacote inicial de specs:

```txt
/docs/specs/
  00-agentdesk-master-spec.md
  01-core-orchestrator.md
  02-agent-runtime.md
  03-model-providers.md
  04-tools-permissions.md
  05-memory-system.md
  06-mcp-integration.md
  07-skills-plugins.md
  08-teams-agents.md
  09-domain-model.md
  10-local-storage.md
  11-execution-logs-audit.md
  12-desktop-frontend.md
  13-plugin-sdk.md
  14-packaging-windows.md
  15-testing-strategy.md
```

A spec `09-domain-model.md` deve ser considerada a fonte da verdade para entidades, nomes, estados e relações.

---

## 3. Objetivo do plano

Este plano define a ordem de implementação do AgentDesk do zero até o MVP funcional.

O objetivo não é implementar tudo de uma vez, mas criar uma sequência segura onde cada fase entrega uma parte testável da plataforma.

A implementação deve priorizar:

1. Contratos de domínio.
2. Armazenamento local.
3. Providers de modelo.
4. Runtime de agente.
5. Orquestrador.
6. Tools e permissões.
7. Timeline/logs.
8. Frontend desktop.
9. Memória.
10. Times.
11. MCP.
12. Skills/plugins.
13. Packaging Windows.
14. Testes e estabilização.

---

## 4. Fora de escopo do MVP

Ficam fora do MVP:

* Marketplace remoto de plugins/skills.
* Suporte oficial a Linux/macOS.
* Multiusuário com login.
* Sincronização em nuvem.
* Backup automático em nuvem.
* Auto-update do Electron.
* Sandboxing avançado de plugins.
* Estratégias multiagente avançadas como debate, swarm, voting ou parallel executor.
* MCP via HTTP/SSE/WebSocket.
* Execução distribuída em múltiplas máquinas.
* Store pública de agentes.
* Controle financeiro de uso por usuário.
* Sistema de permissões hierárquico multiusuário.

---

## 5. Decisões arquiteturais fixadas

### 5.1 Stack

```txt
Desktop: Electron
Frontend: React + TypeScript + Vite + TailwindCSS
Backend: Python + FastAPI
Banco: SQLite
Migrações: Alembic
ORM: SQLAlchemy
Embeddings: Ollama
Modelos locais: Ollama
Modelos remotos: OpenRouter
Eventos em tempo real: SSE no MVP
Packaging: electron-builder + backend empacotado
```

### 5.2 Diretório local

Todos os dados locais ficam em:

```txt
%APPDATA%/AgentDesk/
```

### 5.3 Backend embutido

O Electron deve iniciar o backend FastAPI como subprocesso local.

O backend deve escutar apenas em:

```txt
127.0.0.1
```

Porta sugerida:

```txt
8765
```

Se a porta estiver ocupada, o sistema pode escolher outra porta local e informar ao frontend.

### 5.4 Orquestrador próprio

O AgentDesk não deve depender de LangGraph, CrewAI ou frameworks equivalentes para o core.

A orquestração deve ser própria, simples, auditável e controlável.

### 5.5 Auto-approval

O modo auto-approval deve ser realmente automático.

Isso significa:

* Nenhuma ação deve pedir confirmação durante a execução.
* Tools críticas executam sem modal.
* Terminal executa sem modal.
* Escrita/deleção executa sem modal.
* MCP/plugin tools críticas executam sem modal.

Porém, auto-approval não significa ignorar configuração estrutural do sistema.

O agente ainda só pode usar:

* Tools atribuídas a ele.
* Capabilities atribuídas a ele.
* Workspaces disponíveis para a execução.
* MCPs/plugins habilitados para ele.

Se o usuário quiser liberdade total, deve poder configurar explicitamente um agente/time com acesso amplo.

O auto-approval remove confirmações, não remove a necessidade de configuração.

### 5.6 Manual approval

No modo manual, ações críticas devem pausar a execução e aguardar aprovação do usuário.

A execução entra em:

```txt
waiting_approval
```

Ao aprovar, continua.

Ao recusar, o runtime recebe o erro/negação e deve tentar responder de forma útil ao usuário.

---

## 6. Arquitetura macro

```txt
AgentDesk/
  apps/
    desktop/                 # Electron
    frontend/                # React/Vite/Tailwind

  backend/
    app/
      api/                   # FastAPI routes
      core/                  # settings, app lifecycle, DI
      domain/                # Pydantic schemas/enums/domain models
      db/                    # SQLAlchemy, Alembic, repositories
      providers/             # Ollama/OpenRouter
      runtime/               # Agent Runtime
      orchestrator/          # Core Orchestrator + Team Orchestrator
      tools/                 # Core Tools + Registry
      permissions/           # Permission Gate
      memory/                # Memory System + Embeddings
      mcp/                   # MCP stdio client
      skills/                # Skills registry/loader
      plugins/               # Plugin registry/runner/sdk
      audit/                 # Audit logs/events
      storage/               # AppData manager/backups
      tests/

  docs/
    specs/
    plans/
```

---

## 7. Módulos principais

### 7.1 Domain Layer

Responsável por definir entidades e contratos.

Inclui:

* Agent
* Team
* Execution
* ExecutionEvent
* Tool
* Capability
* Workspace
* Memory
* Skill
* Plugin
* MCPServer
* ApprovalRequest
* AuditLog
* Provider
* ModelConfig

Essa camada deve ser implementada antes das rotas e antes da lógica de execução.

---

### 7.2 Local Storage

Responsável por:

* Criar `%APPDATA%/AgentDesk`.
* Criar estrutura de pastas.
* Criar banco SQLite.
* Rodar migrations.
* Criar configs JSON default.
* Gerenciar backup/restore futuramente.

---

### 7.3 Model Providers

Responsável por:

* Ollama chat.
* Ollama streaming.
* Ollama embeddings.
* OpenRouter chat.
* OpenRouter streaming.
* Health check.
* Listagem de modelos.
* Erros padronizados.

---

### 7.4 Agent Runtime

Responsável por executar um agente individual.

Ele monta contexto com:

* System prompt base.
* System prompt do agente.
* Modo de operação.
* Tools disponíveis.
* Skills ativas.
* Memórias relevantes.
* Histórico recente.
* Solicitação do usuário.

O runtime não executa tools diretamente.

Ele emite intenções estruturadas para o Orchestrator.

---

### 7.5 Core Orchestrator

Responsável por:

* Criar execução.
* Controlar estado.
* Acionar runtime.
* Interceptar tool calls.
* Passar tool calls pelo Permission Gate.
* Pausar em manual approval.
* Continuar após aprovação.
* Emitir eventos SSE.
* Registrar logs.
* Finalizar execução.

---

### 7.6 Tools & Permission Gate

Responsável por:

* Registrar core tools.
* Registrar plugin tools.
* Registrar MCP tools.
* Resolver capabilities.
* Aplicar blocked_tools.
* Validar workspaces.
* Aplicar modo manual/auto.
* Executar tool autorizada.
* Registrar auditoria.

Core tools obrigatórias no MVP:

```txt
filesystem.list
filesystem.read
filesystem.write
filesystem.delete
filesystem.move
filesystem.copy
filesystem.stat
filesystem.search

workspace.list
workspace.get
workspace.scan

memory.search
memory.create
memory.update
memory.delete

agent.list
agent.call

team.list
team.execute

terminal.exec

http.request

logs.search
logs.get_execution
```

---

### 7.7 Execution Events & Audit

Responsável por:

* Eventos em tempo real.
* Timeline do frontend.
* Histórico de execuções.
* Audit logs.
* Mascaramento de segredos.
* Export de logs.

---

### 7.8 Memory System

Responsável por:

* Memória global.
* Memória por agente.
* Memória por time.
* Embeddings locais via Ollama.
* Busca semântica.
* Busca textual.
* Busca híbrida.
* Deduplicação básica.
* Links entre memórias.
* Registro de uso de memória.

---

### 7.9 Teams

Responsável por:

* Criar times.
* Definir agente chefe.
* Adicionar membros.
* Executar estratégia `leader_managed`.
* Permitir delegação.
* Mostrar comunicação operacional.
* Consolidar resposta final.

---

### 7.10 MCP Integration

Responsável por:

* Cadastro manual de servidores MCP.
* Transporte `stdio`.
* Teste de conexão.
* Listagem de tools MCP.
* Registro no Tool Registry.
* Execução via Permission Gate.
* Auditoria.

---

### 7.11 Skills & Plugins

Responsável por:

* Criar skills locais.
* Importar/exportar skills.
* Injetar skills no prompt.
* Importar plugins por pasta.
* Validar `plugin.json`.
* Registrar plugin tools.
* Executar plugin tools via subprocess.
* Registrar logs.

No MVP, plugins Python devem rodar com restrição de ambiente simples.

Dependências externas via `pip install` não devem ser priorizadas no MVP.

---

### 7.12 Desktop Frontend

Responsável por:

* Dashboard.
* Agents.
* Teams.
* Executions.
* Timeline.
* Approvals.
* Memory.
* Workspaces.
* Tools.
* MCP.
* Skills.
* Plugins.
* Providers.
* Settings.
* Audit Logs.

---

## 8. Contratos críticos de execução

### 8.1 Tool call

O modelo deve retornar intenção estruturada.

Formato inicial:

```json
{
  "type": "tool_call",
  "tool": "terminal.exec",
  "arguments": {
    "command": "git status",
    "cwd": "C:/Projetos/app",
    "timeout_seconds": 60
  }
}
```

### 8.2 Subagent call

```json
{
  "type": "subagent_call",
  "target_agent_id": "agent_researcher",
  "task": "Pesquise os arquivos grandes no workspace informado."
}
```

### 8.3 Final answer

```json
{
  "type": "final_answer",
  "content": "Resultado final para o usuário."
}
```

Se o modelo retornar texto comum, o Runtime pode tratar como resposta final.

---

## 9. Regras de segurança

### 9.1 Sem execução direta pelo modelo

O modelo nunca executa comandos diretamente.

O modelo apenas solicita ações.

Toda ação passa por:

```txt
Agent Runtime
  -> Core Orchestrator
    -> Permission Gate
      -> Tool Runner
        -> Audit Logger
```

### 9.2 Workspaces

Filesystem e terminal devem respeitar workspaces.

O sistema deve normalizar caminhos com `pathlib.Path.resolve()`.

Acesso fora do workspace deve falhar.

### 9.3 Terminal

`terminal.exec` é obrigatório no MVP.

Regras:

* `cwd` deve estar dentro de workspace autorizado.
* Timeout obrigatório.
* stdout/stderr truncados nos eventos.
* logs completos podem ser salvos como artefato.
* comando completo aparece na timeline/auditoria.
* em manual approval, pede aprovação.
* em auto approval, executa direto.

### 9.4 Segredos

Nunca salvar em logs:

* API keys completas.
* Authorization headers.
* Cookies.
* Tokens.
* Senhas.
* Chaves privadas.

Função obrigatória:

```python
mask_secrets(data)
```

---

## 10. Ordem de implementação

## Fase 0 — Preparação do repositório e docs

### Objetivo

Criar a base do repositório, salvar specs e preparar estrutura inicial.

### Entregas

* Criar monorepo.
* Criar `/docs/specs`.
* Criar `/docs/plans`.
* Salvar specs.
* Criar README inicial.
* Criar `.gitignore`.
* Criar estrutura de backend/frontend/electron.

### Critério de aceite

* Repositório abre sem erro.
* Estrutura base está criada.
* Specs estão versionadas.
* README explica visão e stack.

---

## Fase 1 — Domain Model e contratos

### Objetivo

Implementar os contratos centrais antes de qualquer lógica complexa.

### Entregas

* Enums de domínio.
* Schemas Pydantic.
* Tipos compartilhados quando possível.
* Modelos SQLAlchemy iniciais.
* DTOs de API.
* Contratos de eventos.
* Contratos de tool call.

### Critério de aceite

* Entidades principais existem.
* Estados de execução estão definidos.
* Schemas validam dados corretamente.
* Testes unitários dos schemas passam.

---

## Fase 2 — Local Storage e AppData

### Objetivo

Criar infraestrutura local.

### Entregas

* AppData manager.
* Criação automática de diretórios.
* SQLite.
* Alembic.
* Migrations iniciais.
* Configs JSON default.
* Repositories básicos.
* Endpoint `/api/health`.
* Endpoint `/api/storage/info`.

### Critério de aceite

* App cria `%APPDATA%/AgentDesk`.
* Banco é criado.
* Migrations rodam no startup.
* Configs default são criadas.
* Health check retorna `ok`.

---

## Fase 3 — Backend API Shell

### Objetivo

Criar a estrutura FastAPI com rotas CRUD base.

### Entregas

Rotas iniciais:

```txt
/api/agents
/api/teams
/api/workspaces
/api/providers
/api/tools
/api/executions
/api/memories
/api/settings
```

Ainda sem IA real.

### Critério de aceite

* CRUD básico de agentes funciona.
* CRUD básico de workspaces funciona.
* CRUD básico de providers funciona.
* API gera OpenAPI sem erro.
* Testes de API passam.

---

## Fase 4 — Model Providers

### Objetivo

Implementar Ollama e OpenRouter.

### Entregas

* Provider interface.
* Ollama health check.
* Ollama list models.
* Ollama chat.
* Ollama streaming.
* Ollama embeddings.
* OpenRouter health check.
* OpenRouter chat.
* OpenRouter streaming.
* Erros padronizados.
* Mascaramento de API key.

### Critério de aceite

* Ollama local responde se estiver rodando.
* Modelos locais são listados.
* Chat Ollama funciona.
* Streaming Ollama funciona.
* Embeddings Ollama funcionam.
* OpenRouter funciona com API key configurada.
* API key não aparece em logs.

---

## Fase 5 — Execution Engine básico sem tools

### Objetivo

Executar agente individual usando modelo real ou provider mock, sem tools ainda.

### Entregas

* Agent Runtime inicial.
* Prompt builder.
* Context builder.
* Execution creation.
* Execution status.
* SSE básico.
* Timeline básica.
* Final answer.
* Histórico de execução.

### Critério de aceite

* Usuário consegue criar execução de agente.
* Runtime chama modelo.
* Resposta aparece como evento.
* Execution termina como `completed`.
* Erros de provider marcam execution como `failed`.

---

## Fase 6 — Frontend Shell inicial

### Objetivo

Criar o app desktop/visual mínimo para operar o backend.

### Entregas

* Electron inicia frontend.
* Frontend conecta ao backend.
* Sidebar.
* Dashboard simples.
* Tela Agents.
* Tela Providers.
* Tela Workspaces.
* Tela Executions.
* Tela de execução com SSE.
* Estado de erro se backend não iniciar.

### Critério de aceite

* App abre como desktop.
* Backend é detectado.
* Usuário cria agente pela UI.
* Usuário configura provider pela UI.
* Usuário executa agente pela UI.
* Timeline mostra eventos.

---

## Fase 7 — Tool Registry e Core Tools de leitura

### Objetivo

Adicionar tools nativas sem ações destrutivas.

### Entregas

* Tool Registry.
* Capabilities.
* Permission Gate inicial.
* `filesystem.list`.
* `filesystem.read`.
* `filesystem.stat`.
* `filesystem.search`.
* `workspace.list`.
* `workspace.get`.
* `logs.search`.
* Registro de tool events.
* Bloqueio fora do workspace.

### Critério de aceite

* Agent com capability consegue listar workspace.
* Agent sem capability não consegue.
* Acesso fora do workspace é bloqueado.
* Tool call aparece na timeline.
* Audit log é criado.

---

## Fase 8 — Tools críticas e approval flow

### Objetivo

Adicionar escrita, deleção e terminal com manual/auto approval.

### Entregas

* `filesystem.write`.
* `filesystem.delete`.
* `filesystem.move`.
* `filesystem.copy`.
* `terminal.exec`.
* `http.request`.
* ApprovalRequest.
* Estado `waiting_approval`.
* Endpoint de aprovação.
* UI de aprovação.
* Auto-approval sem modal.
* Logs detalhados de terminal.

### Critério de aceite

* Em modo manual, terminal pede aprovação.
* Em modo auto, terminal executa direto.
* Em modo manual, escrita/deleção pede aprovação.
* Em modo auto, escrita/deleção executa direto.
* stdout/stderr aparecem de forma segura.
* Audit log é salvo.
* Nenhum segredo aparece em log.

---

## Fase 9 — Memory System

### Objetivo

Implementar o cérebro local do sistema.

### Entregas

* Tabelas de memória.
* CRUD de memória.
* Embeddings via Ollama.
* Busca textual.
* Busca semântica.
* Busca híbrida simples.
* Escopos global/agent/team.
* Deduplicação básica.
* Links entre memórias.
* Memórias usadas no prompt.
* Tela Memory.

### Critério de aceite

* Usuário cria memória global.
* Usuário cria memória de agente.
* Runtime recupera memórias relevantes.
* Embeddings são gerados localmente.
* Busca semântica funciona.
* Memória usada aparece na timeline.

---

## Fase 10 — Subagentes e Teams

### Objetivo

Implementar colaboração multiagente.

### Entregas

* `agent.call`.
* `agent.list`.
* Criação de times.
* Agente chefe.
* Membros.
* Estratégia `leader_managed`.
* Delegação.
* Timeline de comunicação operacional.
* Memória de time.
* Tela Teams.

### Critério de aceite

* Agente consegue chamar subagente.
* Time consegue executar solicitação.
* Agente chefe cria plano.
* Membros respondem.
* Chefe consolida resposta final.
* Timeline mostra colaboração.
* Logs registram todos os agentes envolvidos.

---

## Fase 11 — Skills

### Objetivo

Adicionar comportamentos reutilizáveis via prompt/template.

### Entregas

* CRUD de skills.
* Import/export JSON.
* Associação de skill a agente.
* Associação de skill a time.
* Injeção no prompt.
* Tela Skills.

### Critério de aceite

* Usuário cria skill.
* Skill é atribuída a agente.
* Skill aparece no prompt builder.
* Resultado do agente respeita a skill.

---

## Fase 12 — Plugin SDK MVP

### Objetivo

Permitir plugins locais por pasta.

### Entregas

* Validação de `plugin.json`.
* Importação por pasta.
* Registro de plugin.
* Registro de plugin tools.
* Registro de plugin skills.
* Plugin Runner via Python subprocess.
* Timeout.
* Logs.
* Tela Plugins.

### Critério de aceite

* Plugin local válido é importado.
* Plugin inválido é rejeitado.
* Plugin tool aparece no Tool Registry.
* Agent consegue usar plugin tool autorizada.
* Plugin tool respeita approval mode.
* Plugin tool gera audit log.

---

## Fase 13 — MCP stdio

### Objetivo

Adicionar integração MCP manual.

### Entregas

* CRUD de MCP servers.
* Configuração stdio.
* Test connection.
* List tools.
* Registro de MCP tools.
* Execução de MCP tool via Permission Gate.
* Tela MCP Servers.

### Critério de aceite

* Usuário cadastra MCP stdio.
* Sistema lista tools.
* Agent autorizado usa MCP tool.
* Chamada aparece na timeline.
* Chamada gera audit log.

---

## Fase 14 — Audit Logs, histórico e export

### Objetivo

Consolidar rastreabilidade.

### Entregas

* Tela Audit Logs.
* Filtros.
* Detalhe de execução.
* Export JSON.
* Cleanup de logs.
* Retenção configurável.
* Melhorias de timeline.

### Critério de aceite

* Todas as execuções aparecem no histórico.
* Toda tool gera audit log.
* Toda aprovação gera audit log.
* Auto-approval também gera audit log.
* Logs podem ser filtrados.
* Execução pode ser exportada como JSON.

---

## Fase 15 — Packaging Windows

### Objetivo

Gerar app desktop instalável.

### Entregas

* Electron main process.
* Inicialização do backend empacotado.
* Build frontend.
* Build backend com PyInstaller.
* electron-builder.
* NSIS installer.
* Portable build.
* Logs de startup.
* Encerramento seguro do backend.

### Critério de aceite

* App instala no Windows.
* App abre como desktop.
* Backend inicia automaticamente.
* Frontend conecta.
* AppData é criado.
* App fecha sem deixar processo preso.
* Build portable funciona.
* Installer funciona.

---

## Fase 16 — Testes, hardening e polish

### Objetivo

Estabilizar MVP.

### Entregas

* Testes unitários backend.
* Testes de API.
* Testes de tool safety.
* Testes de provider mock.
* Testes de memory.
* Testes de plugin.
* Testes MCP mock.
* Testes frontend.
* E2E básico.
* Smoke test de packaging.
* Ajustes UX.
* README final.
* Guia de contribuição.

### Critério de aceite

* Fluxo criar agente/executar funciona.
* Fluxo terminal manual funciona.
* Fluxo terminal auto funciona.
* Fluxo time leader_managed funciona.
* Fluxo memory funciona.
* Fluxo plugin funciona.
* Fluxo MCP funciona.
* Build Windows funciona.
* README explica instalação e uso.

---

## 11. Critérios de aceite do MVP completo

O MVP será considerado completo quando:

* O app desktop iniciar no Windows.
* O backend FastAPI iniciar embutido no Electron.
* O AppData for criado automaticamente.
* SQLite e migrations funcionarem.
* O usuário conseguir configurar Ollama.
* O usuário conseguir configurar OpenRouter.
* O usuário conseguir criar agentes.
* O usuário conseguir configurar modelo por agente.
* O usuário conseguir configurar tools/capabilities por agente.
* O usuário conseguir criar workspaces.
* O usuário conseguir executar agente individual.
* O agente conseguir usar tools autorizadas.
* O terminal funcionar como tool.
* Manual approval pausar execução.
* Auto-approval executar sem confirmação.
* O usuário conseguir criar times.
* O agente chefe conseguir delegar para membros.
* Timeline mostrar eventos em tempo real.
* Memória global/agente/time funcionar.
* Embeddings locais funcionarem via Ollama.
* Skills locais funcionarem.
* Plugins locais funcionarem.
* MCP stdio funcionar.
* Logs/auditoria serem salvos.
* Segredos serem mascarados.
* O app gerar build Windows instalável ou portable.

---

## 12. Riscos e mitigação

| Risco                                                 | Impacto | Mitigação                                                                                 |
| ----------------------------------------------------- | ------: | ----------------------------------------------------------------------------------------- |
| MVP grande demais                                     |    Alto | Implementar por fases com critérios de aceite claros. Não misturar módulos.               |
| Terminal executar ação perigosa                       |    Alto | Permission Gate, workspace validation, audit logs e modo manual por padrão.               |
| Auto-approval causar ações indesejadas                |    Alto | Auto-approval deve ser explícito e visualmente destacado. Logs sempre obrigatórios.       |
| Plugins executarem código inseguro                    |    Alto | Aviso na instalação, permissões declaradas, logs, timeout e sandbox futuro.               |
| MCP instável                                          |   Médio | Começar apenas com stdio e mocks de teste.                                                |
| Modelos locais pequenos falharem em tarefas complexas |   Médio | Prompts estruturados, tool calls determinísticas, contexto limitado e memórias compactas. |
| SQLite crescer demais com logs                        |   Médio | Retenção configurável e export/cleanup.                                                   |
| SSE travar ou perder conexão                          |   Médio | Endpoint de histórico para reconstruir timeline.                                          |
| Provider indisponível                                 |   Médio | Health checks e erros amigáveis.                                                          |
| Specs divergirem durante implementação                |   Médio | Domain Model como fonte da verdade. Mudanças arquiteturais só via atualização de spec.    |

---

## 13. Decisões técnicas finais

### 13.1 Usar Alembic

O projeto deve usar Alembic para migrações SQLite.

As migrations devem rodar automaticamente no startup do backend.

### 13.2 Usar SQLAlchemy

SQLAlchemy deve ser usado para persistência relacional.

### 13.3 Usar Pydantic

Pydantic deve validar schemas de API e contratos internos.

### 13.4 Não usar framework multiagente externo no core

O orquestrador será próprio.

Bibliotecas auxiliares podem ser usadas, mas não devem controlar o fluxo principal.

### 13.5 Usar SSE no MVP

SSE é suficiente para timeline e eventos.

WebSocket pode ficar para futuro.

### 13.6 Plugin Runner simples no MVP

Plugins Python rodam via subprocess.

Sem marketplace.

Sem sandbox avançado.

Sem suporte obrigatório a dependências externas via pip no MVP.

### 13.7 Manual approval como padrão

O modo padrão do sistema deve ser `manual`.

O modo `auto` deve ser escolha explícita do usuário na execução/configuração.

---

## 14. Roadmap resumido

```txt
Fase 0  — Repositório e docs
Fase 1  — Domain Model
Fase 2  — Local Storage e AppData
Fase 3  — Backend API Shell
Fase 4  — Model Providers
Fase 5  — Execution Engine sem tools
Fase 6  — Frontend Shell
Fase 7  — Tool Registry e tools de leitura
Fase 8  — Tools críticas e approval flow
Fase 9  — Memory System
Fase 10 — Subagentes e Teams
Fase 11 — Skills
Fase 12 — Plugin SDK MVP
Fase 13 — MCP stdio
Fase 14 — Audit Logs e export
Fase 15 — Packaging Windows
Fase 16 — Testes, hardening e polish
```

---

## 15. Checklist antes de implementar

* [ ] Specs salvas em `/docs/specs`.
* [ ] Este plano salvo em `/docs/plans/implementation-roadmap.md`.
* [ ] README inicial criado.
* [ ] Repositório Git iniciado.
* [ ] Domain Model revisado.
* [ ] Decisão confirmada: manual approval como padrão.
* [ ] Decisão confirmada: auto-approval sem confirmações.
* [ ] Decisão confirmada: terminal tool no MVP.
* [ ] Decisão confirmada: Ollama + OpenRouter no MVP.
* [ ] Decisão confirmada: MCP apenas stdio no MVP.
* [ ] Decisão confirmada: plugins locais por pasta no MVP.
* [ ] Decisão confirmada: Windows-first.

---

## 16. Prompt sugerido para iniciar a implementação

Use o prompt abaixo com o agente de código:

```txt
Leia todas as specs em /docs/specs e o plano em /docs/plans/implementation-roadmap.md.

Você deve implementar o AgentDesk seguindo estritamente as specs e o plano.

Não comece pela interface completa.
Comece pela Fase 0, Fase 1 e Fase 2.

Objetivo inicial:
1. Criar a estrutura do monorepo.
2. Criar o backend FastAPI.
3. Criar o Domain Model com Pydantic e SQLAlchemy.
4. Criar o AppData manager.
5. Criar SQLite com Alembic.
6. Criar configs JSON default.
7. Criar /api/health e /api/storage/info.
8. Criar testes unitários mínimos.

Regras:
- Não implemente features fora das specs.
- Não adicione marketplace.
- Não adicione login.
- Não adicione cloud sync.
- Não use framework multiagente externo no core.
- Não implemente terminal ainda.
- Não implemente MCP ainda.
- Não implemente plugins ainda.
- Não implemente frontend completo ainda.
- Toda decisão nova deve ser documentada em /docs/decisions.
- Se houver conflito entre specs, use 09-domain-model.md como fonte da verdade.
- Se algo estiver ambíguo, escolha a solução mais simples compatível com o MVP.
```
