# 01-core-orchestrator.md

# AgentDesk — Core Orchestrator Spec

## 1. Objetivo

O Core Orchestrator é o coração do AgentDesk.

Ele é responsável por coordenar execuções entre agentes, subagentes, times, ferramentas, memória, permissões e eventos visíveis no frontend.

O orquestrador não deve depender do Electron nem do React.

Ele deve funcionar como um módulo backend puro, consumido por rotas FastAPI e futuramente por outros clientes.

---

## 2. Responsabilidades

O Core Orchestrator deve:

* Receber uma solicitação do usuário.
* Identificar se a execução é de agente individual ou time.
* Criar uma execução rastreável.
* Carregar configurações do agente/time.
* Inicializar contexto.
* Acionar o Agent Runtime.
* Coordenar subagentes.
* Coordenar agente chefe em times.
* Aplicar regras de permissão.
* Emitir eventos em tempo real.
* Registrar logs e auditoria.
* Retornar resultado final.

---

## 3. Não Responsabilidades

O Core Orchestrator não deve:

* Implementar diretamente chamadas para Ollama/OpenRouter.
* Implementar UI.
* Executar tools diretamente sem passar pelo sistema de tools/permissões.
* Armazenar memória diretamente sem usar o Memory System.
* Conhecer detalhes internos de MCP.
* Conhecer detalhes internos de plugins.

---

## 4. Entidades Principais

### Execution

Representa uma execução iniciada pelo usuário.

Campos mínimos:

```json
{
  "id": "exec_001",
  "type": "agent | team",
  "status": "pending | running | waiting_approval | completed | failed | cancelled",
  "user_input": "string",
  "target_id": "agent_id_or_team_id",
  "created_at": "datetime",
  "updated_at": "datetime",
  "completed_at": "datetime | null",
  "approval_mode": "manual | auto",
  "result": "string | null",
  "error": "string | null"
}
```

### ExecutionEvent

Evento emitido durante a execução.

```json
{
  "id": "event_001",
  "execution_id": "exec_001",
  "type": "message | tool_call | tool_result | approval_request | approval_result | memory_lookup | memory_write | subagent_call | status | error",
  "source": "user | orchestrator | agent | subagent | tool | memory | mcp",
  "source_id": "optional_id",
  "content": {},
  "created_at": "datetime"
}
```

### ExecutionContext

Contexto operacional da execução.

```json
{
  "execution_id": "exec_001",
  "approval_mode": "manual | auto",
  "workspace_ids": [],
  "agent_stack": [],
  "memory_scope": {
    "global": true,
    "team_id": null,
    "agent_id": "agent_001"
  },
  "variables": {},
  "limits": {
    "max_steps": 30,
    "max_subagent_depth": 5,
    "max_tool_calls": 100
  }
}
```

---

## 5. Fluxo de Execução — Agente Individual

1. Usuário envia mensagem para um agente.
2. Orquestrador cria `Execution`.
3. Orquestrador carrega configuração do agente.
4. Orquestrador monta `ExecutionContext`.
5. Orquestrador solicita contexto relevante ao Memory System.
6. Orquestrador chama o Agent Runtime.
7. Runtime processa modelo/tools.
8. Orquestrador recebe eventos.
9. Se houver tool crítica:

   * no modo manual, solicita aprovação;
   * no modo auto, executa direto.
10. Orquestrador salva logs.
11. Orquestrador retorna resultado final.

---

## 6. Fluxo de Execução — Time de Agentes

1. Usuário envia solicitação para um time.
2. Orquestrador cria `Execution`.
3. Orquestrador carrega configuração do time.
4. Orquestrador identifica agente chefe.
5. Agente chefe recebe a solicitação.
6. Agente chefe cria plano de execução.
7. Orquestrador permite que o chefe acione agentes membros.
8. Cada agente membro executa sua parte.
9. Eventos são emitidos para timeline.
10. Agente chefe revisa respostas.
11. Agente chefe consolida resultado final.
12. Orquestrador salva logs.
13. Resultado é retornado ao usuário.

---

## 7. Subagentes

Um agente pode chamar subagentes livremente.

Regras:

* Subagentes devem gerar eventos visíveis.
* Subagentes herdam o modo de aprovação da execução.
* Subagentes podem ter modelos diferentes.
* Subagentes usam suas próprias tools habilitadas.
* Subagentes podem acessar memória própria e memória global.
* Subagentes não devem ultrapassar limite de profundidade definido em `ExecutionContext`.

Exemplo de evento:

```json
{
  "type": "subagent_call",
  "source": "agent",
  "source_id": "agent_researcher",
  "content": {
    "target_agent_id": "agent_writer",
    "task": "Resumir os pontos principais encontrados"
  }
}
```

---

## 8. Aprovações

O orquestrador deve centralizar aprovações.

### Modo Manual

Quando uma tool exigir aprovação:

1. Criar evento `approval_request`.
2. Pausar execução.
3. Aguardar resposta do usuário.
4. Continuar ou cancelar ação.

### Modo Auto

Nenhuma aprovação deve ser solicitada.

A ação deve ser executada diretamente.

Mesmo assim, deve ser registrado evento de auditoria.

---

## 9. Eventos em Tempo Real

O frontend deve receber eventos da execução.

Inicialmente usar:

* Server-Sent Events, ou
* WebSocket.

Recomendação inicial: SSE para simplicidade.

Endpoint sugerido:

```txt
GET /api/executions/{execution_id}/events
```

---

## 10. API Inicial

### Criar execução de agente

```txt
POST /api/executions/agent
```

Body:

```json
{
  "agent_id": "agent_001",
  "message": "Organize meus arquivos grandes",
  "approval_mode": "manual",
  "workspace_ids": ["workspace_001"]
}
```

### Criar execução de time

```txt
POST /api/executions/team
```

Body:

```json
{
  "team_id": "team_001",
  "message": "Pesquise, analise e crie um relatório",
  "approval_mode": "auto",
  "workspace_ids": ["workspace_001"]
}
```

### Buscar execução

```txt
GET /api/executions/{execution_id}
```

### Cancelar execução

```txt
POST /api/executions/{execution_id}/cancel
```

### Responder aprovação

```txt
POST /api/executions/{execution_id}/approvals/{approval_id}
```

Body:

```json
{
  "approved": true
}
```

---

## 11. Estados da Execução

Estados possíveis:

```txt
pending
running
waiting_approval
completed
failed
cancelled
```

Transições:

```txt
pending -> running
running -> waiting_approval
waiting_approval -> running
running -> completed
running -> failed
running -> cancelled
waiting_approval -> cancelled
```

---

## 12. Persistência

O orquestrador deve salvar:

* Execuções.
* Eventos.
* Aprovações.
* Resultado final.
* Erros.
* Chamadas de tools.
* Chamadas de subagentes.

Banco sugerido: SQLite.

Tabelas iniciais:

```txt
executions
execution_events
execution_approvals
execution_artifacts
```

---

## 13. Contratos com Outros Módulos

### Agent Runtime

O orquestrador chama o runtime com:

```python
run_agent(agent_config, execution_context, message)
```

### Tools System

O orquestrador solicita execução de tool com:

```python
execute_tool(tool_name, args, execution_context)
```

### Memory System

O orquestrador solicita contexto com:

```python
search_memory(query, scopes)
```

E salva memórias com:

```python
create_memory(memory_data)
```

### Model Providers

O orquestrador não chama providers diretamente.

Essa responsabilidade é do Agent Runtime.

---

## 14. Critérios de Aceite

O Core Orchestrator estará pronto quando:

* Conseguir criar execução de agente.
* Conseguir criar execução de time.
* Conseguir emitir eventos em tempo real.
* Conseguir pausar execução para aprovação.
* Conseguir rodar em modo auto aprovação.
* Conseguir registrar logs completos.
* Conseguir coordenar subagentes.
* Conseguir cancelar execução.
* Conseguir recuperar histórico de execução.
* Funcionar sem depender do frontend.
