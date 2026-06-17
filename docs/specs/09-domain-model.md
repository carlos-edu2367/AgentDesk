# 09-domain-model.md

# AgentDesk — Domain Model Spec

## 1. Objetivo

Este documento define o modelo de domínio oficial do AgentDesk.

Ele serve como fonte de verdade para backend, frontend, banco de dados, plugins, logs e integrações futuras.

Todas as specs posteriores devem respeitar as entidades e relações descritas aqui.

---

## 2. Entidades Principais

O AgentDesk possui as seguintes entidades centrais:

```txt
User
Provider
ModelConfig
Agent
Team
Execution
ExecutionEvent
Tool
Capability
Workspace
Memory
Skill
Plugin
MCPServer
ApprovalRequest
AuditLog
```

---

## 3. User

No MVP, o AgentDesk é local e single-user.

Mesmo assim, a entidade `User` deve existir para permitir evolução futura.

```json
{
  "id": "user_local",
  "name": "Local User",
  "created_at": "datetime",
  "settings": {}
}
```

Regras:

* O MVP deve assumir apenas um usuário local.
* Não precisa de login.
* Configurações devem ser associadas ao usuário local.

---

## 4. Provider

Representa um provedor de modelo.

Tipos iniciais:

```txt
ollama
openrouter
```

```json
{
  "id": "provider_ollama_local",
  "type": "ollama",
  "name": "Ollama Local",
  "base_url": "http://localhost:11434",
  "enabled": true,
  "config": {}
}
```

---

## 5. ModelConfig

Configuração de modelo usada por agente.

```json
{
  "provider_id": "provider_ollama_local",
  "model": "qwen3:8b",
  "temperature": 0.4,
  "top_p": 0.9,
  "context_window": 8192,
  "max_tokens": 2048,
  "stream": true
}
```

Regras:

* Cada agente possui uma configuração própria.
* Times não possuem modelo próprio, exceto o modelo dos agentes que compõem o time.
* O agente chefe usa sua própria configuração de modelo.

---

## 6. Agent

Representa uma unidade autônoma configurável.

```json
{
  "id": "agent_001",
  "name": "Assistente Geral",
  "description": "Agente para tarefas gerais.",
  "system_prompt": "Você é um assistente útil.",
  "model_config": {},
  "capabilities": [],
  "explicit_tools": [],
  "blocked_tools": [],
  "skills": [],
  "plugins": [],
  "mcp_servers": [],
  "memory_config": {
    "use_global": true,
    "use_agent_memory": true,
    "use_team_memory": false
  },
  "subagents": {
    "can_call": true,
    "allowed_agent_ids": ["*"]
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Regras:

* Um agente pode chamar subagentes se `can_call = true`.
* Um agente pode usar tools nativas, tools de plugin e tools MCP.
* Um agente pode ter memória própria.
* Um agente pode participar de vários times.

---

## 7. Team

Representa um grupo de agentes coordenado por um agente chefe.

```json
{
  "id": "team_001",
  "name": "Time de Pesquisa e Escrita",
  "description": "Pesquisa, analisa e escreve relatórios.",
  "leader_agent_id": "agent_leader",
  "member_agent_ids": [
    "agent_researcher",
    "agent_writer"
  ],
  "execution_strategy": "leader_managed",
  "memory_config": {
    "use_global": true,
    "use_team_memory": true,
    "allow_member_memories": true
  },
  "tools_policy": {
    "inherit_from_agents": true,
    "additional_capabilities": [],
    "blocked_tools": []
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Regras:

* Todo time deve ter exatamente um agente chefe.
* O agente chefe também pode estar na lista de membros, mas isso não é obrigatório.
* Cada membro mantém suas próprias configurações.
* O time possui memória própria.

---

## 8. Execution

Representa uma execução iniciada pelo usuário.

Pode ser:

```txt
agent
team
```

```json
{
  "id": "exec_001",
  "type": "agent",
  "target_id": "agent_001",
  "user_input": "Analise meus arquivos.",
  "status": "running",
  "approval_mode": "manual",
  "workspace_ids": [],
  "created_at": "datetime",
  "updated_at": "datetime",
  "completed_at": null,
  "result": null,
  "error": null
}
```

Estados possíveis:

```txt
pending
running
waiting_approval
completed
failed
cancelled
```

---

## 9. ExecutionEvent

Evento emitido durante uma execução.

```json
{
  "id": "event_001",
  "execution_id": "exec_001",
  "type": "tool_call",
  "source": "agent",
  "source_id": "agent_001",
  "content": {},
  "created_at": "datetime"
}
```

Tipos principais:

```txt
message
status
model_chunk
tool_call
tool_result
approval_request
approval_result
memory_lookup
memory_write
subagent_call
team_event
error
```

---

## 10. Tool

Representa uma ferramenta executável.

```json
{
  "name": "filesystem.read",
  "description": "Lê um arquivo dentro de um workspace permitido.",
  "source": "core",
  "capability": "filesystem_read",
  "critical": false,
  "input_schema": {},
  "output_schema": {}
}
```

Sources possíveis:

```txt
core
plugin
mcp
```

Regras:

* Tools devem ter namespace.
* Core tools não podem ser sobrescritas.
* Plugin tools devem usar namespace próprio.
* MCP tools seguem o padrão `mcp.{server_id}.{tool_name}`.

---

## 11. Capability

Agrupamento de tools.

```json
{
  "id": "filesystem_read",
  "name": "Filesystem Read",
  "description": "Permite leitura de arquivos e diretórios.",
  "tools": [
    "filesystem.list",
    "filesystem.read",
    "filesystem.stat"
  ]
}
```

Regras:

* Agentes devem ser configurados preferencialmente por capabilities.
* `blocked_tools` sempre vence.
* Capabilities melhoram a UX e evitam listas enormes de tools.

---

## 12. Workspace

Representa uma área do filesystem autorizada pelo usuário.

```json
{
  "id": "workspace_001",
  "name": "Projetos",
  "paths": [
    "C:/Users/Carlos/Documents/Projetos"
  ],
  "permissions": {
    "read": true,
    "write": true,
    "delete": false,
    "execute": false
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Regras:

* Agentes só podem acessar arquivos dentro de workspaces autorizados.
* Terminal deve executar preferencialmente dentro de um workspace.
* Caminhos devem ser normalizados.
* Acesso fora do workspace deve ser bloqueado.

---

## 13. Memory

Representa uma memória persistente.

```json
{
  "id": "mem_001",
  "scope": "global",
  "scope_id": null,
  "type": "preference",
  "title": "Preferência de resposta",
  "content": "O usuário prefere respostas diretas.",
  "tags": [],
  "confidence": 0.9,
  "importance": 0.7,
  "source": {},
  "created_at": "datetime",
  "updated_at": "datetime",
  "last_used_at": null,
  "usage_count": 0
}
```

Scopes:

```txt
global
agent
team
workspace
```

Tipos:

```txt
profile
preference
project
file_reference
task_history
decision
lesson
error_pattern
workflow
system_note
```

---

## 14. Skill

Comportamento reutilizável baseado em prompt/template.

```json
{
  "id": "skill_report_writer",
  "name": "Escritor de Relatórios",
  "version": "0.1.0",
  "description": "Ajuda agentes a gerar relatórios.",
  "tags": [],
  "prompt": "Organize relatórios em resumo, achados, riscos e próximos passos.",
  "examples": []
}
```

Regras:

* Skills não executam código.
* Skills são injetadas no prompt.
* Skills podem ser associadas a agentes e times.

---

## 15. Plugin

Pacote local que pode conter skills, tools e configurações.

```json
{
  "id": "plugin_github",
  "name": "GitHub Plugin",
  "version": "0.1.0",
  "description": "Adiciona tools relacionadas ao GitHub.",
  "enabled": true,
  "manifest_path": "",
  "permissions": [],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Regras:

* Plugins podem registrar tools.
* Plugins podem conter skills.
* Plugins devem declarar permissões.
* Plugins devem passar pelo sistema de auditoria.

---

## 16. MCPServer

Servidor MCP configurado pelo usuário.

```json
{
  "id": "mcp_github",
  "name": "GitHub MCP",
  "enabled": true,
  "transport": "stdio",
  "command": "npx",
  "args": [],
  "env": {},
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Regras:

* MVP suporta `stdio`.
* Tools MCP são registradas dinamicamente.
* MCP pode ser habilitado por agente/time.

---

## 17. ApprovalRequest

Solicitação de aprovação para ações críticas.

```json
{
  "id": "approval_001",
  "execution_id": "exec_001",
  "agent_id": "agent_001",
  "tool": "terminal.exec",
  "status": "pending",
  "risk_level": "high",
  "summary": "Executar comando no terminal.",
  "arguments": {},
  "created_at": "datetime",
  "resolved_at": null
}
```

Estados:

```txt
pending
approved
rejected
expired
```

---

## 18. AuditLog

Registro permanente de ação relevante.

```json
{
  "id": "audit_001",
  "execution_id": "exec_001",
  "agent_id": "agent_001",
  "event_type": "tool_executed",
  "summary": "Executou terminal.exec",
  "data": {},
  "created_at": "datetime"
}
```

Regras:

* Toda tool executada gera audit log.
* Aprovações geram audit log.
* Erros críticos geram audit log.
* Auto aprovação também gera audit log.

---

## 19. Relações Entre Entidades

```txt
Agent 1:N Execution
Team 1:N Execution
Execution 1:N ExecutionEvent
Execution 1:N ApprovalRequest
Execution 1:N AuditLog

Agent N:N Skill
Agent N:N Plugin
Agent N:N MCPServer
Agent N:N Workspace

Team N:N Agent
Team N:N Workspace

Plugin 1:N Tool
MCPServer 1:N Tool

Memory pertence a um scope:
- global
- agent
- team
- workspace
```

---

## 20. Critérios de Aceite

Esta spec estará cumprida quando:

* Todas as entidades principais existirem no backend.
* O banco local refletir essas entidades.
* O frontend usar os mesmos nomes/conceitos.
* Specs futuras não criarem entidades conflitantes.
* Agentes, times, execuções, tools, memórias e plugins tiverem contratos claros.
