# 04-tools-permissions.md

# AgentDesk — Tools & Permissions Spec

## 1. Objetivo

O módulo Tools & Permissions define como agentes acessam ferramentas, quais ações podem executar e como o sistema controla permissões, aprovações e auditoria.

O AgentDesk deve usar arquitetura híbrida:

* Core Tools nativas.
* Plugin Tools adicionadas por plugins.
* MCP Tools vindas de servidores MCP.

Para o agente, todas aparecem como tools.

---

## 2. Responsabilidades

O módulo deve:

* Registrar tools nativas.
* Registrar tools vindas de plugins.
* Registrar tools vindas de MCP.
* Expor tools disponíveis por agente.
* Organizar tools por capabilities.
* Validar permissões antes da execução.
* Aplicar modo manual ou auto aprovação.
* Executar tools autorizadas.
* Registrar logs de auditoria.
* Bloquear acesso fora dos workspaces permitidos.
* Suportar terminal nativo no MVP.

---

## 3. Conceitos

### Tool

Uma função executável por agente.

Exemplo:

```txt
filesystem.read
terminal.exec
memory.search
```

### Capability

Agrupamento de tools relacionadas.

Exemplo:

```txt
filesystem_read
filesystem_write
filesystem_delete
terminal
memory
http
mcp
plugins
```

### Permission Policy

Política que define o que um agente pode fazer.

### Approval Mode

Modo de aprovação da execução:

```txt
manual
auto
```

---

## 4. Core Tools do MVP

### Filesystem

```txt
filesystem.list
filesystem.read
filesystem.write
filesystem.delete
filesystem.move
filesystem.copy
filesystem.stat
filesystem.search
```

### Workspace

```txt
workspace.list
workspace.get
workspace.scan
```

### Memory

```txt
memory.search
memory.create
memory.update
memory.delete
```

### Agent

```txt
agent.list
agent.call
```

### Team

```txt
team.list
team.execute
```

### Terminal

```txt
terminal.exec
```

### HTTP

```txt
http.request
```

### Logs

```txt
logs.search
logs.get_execution
```

---

## 5. Capabilities do MVP

```json
{
  "filesystem_read": [
    "filesystem.list",
    "filesystem.read",
    "filesystem.stat",
    "filesystem.search"
  ],
  "filesystem_write": [
    "filesystem.write",
    "filesystem.move",
    "filesystem.copy"
  ],
  "filesystem_delete": [
    "filesystem.delete"
  ],
  "terminal": [
    "terminal.exec"
  ],
  "memory": [
    "memory.search",
    "memory.create",
    "memory.update",
    "memory.delete"
  ],
  "agent_control": [
    "agent.list",
    "agent.call"
  ],
  "team_control": [
    "team.list",
    "team.execute"
  ],
  "http": [
    "http.request"
  ],
  "logs": [
    "logs.search",
    "logs.get_execution"
  ]
}
```

---

## 6. Configuração de Tools por Agente

O agente deve poder receber capabilities e tools específicas.

Exemplo:

```json
{
  "agent_id": "agent_file_manager",
  "capabilities": [
    "filesystem_read",
    "filesystem_write",
    "memory"
  ],
  "explicit_tools": [
    "workspace.scan"
  ],
  "blocked_tools": [
    "filesystem.delete",
    "terminal.exec"
  ]
}
```

Regra:

* `blocked_tools` sempre vence.
* capabilities liberam grupos.
* explicit_tools liberam tools específicas.
* tools inexistentes devem gerar erro claro.

---

## 7. Workspaces

O acesso a filesystem deve respeitar workspaces cadastrados.

Exemplo:

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
  }
}
```

Regras:

* `filesystem.read` só pode ler dentro de workspace permitido.
* `filesystem.write` só pode escrever dentro de workspace permitido.
* `filesystem.delete` só pode deletar dentro de workspace permitido e se delete estiver permitido.
* `terminal.exec` deve rodar preferencialmente dentro de workspace permitido.
* Caminhos devem ser normalizados para evitar path traversal.

---

## 8. Terminal Tool

A tool `terminal.exec` é nativa e obrigatória no MVP.

### Objetivo

Permitir automação local e agentes de código/desenvolvimento.

### Entrada

```json
{
  "command": "git status",
  "cwd": "C:/Users/Carlos/Documents/Projetos/app",
  "timeout_seconds": 60
}
```

### Saída

```json
{
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "duration_ms": 1200
}
```

### Regras

* `cwd` deve estar dentro de workspace autorizado.
* Timeout padrão: 60 segundos.
* Timeout máximo configurável.
* Registrar comando completo em auditoria.
* Registrar stdout/stderr truncado se muito grande.
* Em modo manual, solicitar aprovação antes de executar.
* Em modo auto, executar sem aprovação.
* Nunca ocultar comandos executados.

---

## 9. Ações Críticas

São ações críticas:

```txt
filesystem.write
filesystem.delete
filesystem.move
filesystem.copy
terminal.exec
http.request
memory.delete
plugin.install
plugin.remove
mcp.call
```

No modo manual:

* Devem pedir aprovação.

No modo auto:

* Devem executar sem confirmação.

---

## 10. Approval Request

Formato:

```json
{
  "id": "approval_001",
  "execution_id": "exec_001",
  "tool": "terminal.exec",
  "risk_level": "high",
  "summary": "Executar comando no terminal",
  "arguments": {
    "command": "npm install",
    "cwd": "C:/Projetos/app"
  },
  "created_at": "datetime"
}
```

---

## 11. Auditoria

Toda tool executada deve gerar log.

Campos:

```json
{
  "id": "tool_log_001",
  "execution_id": "exec_001",
  "agent_id": "agent_001",
  "tool": "terminal.exec",
  "arguments": {},
  "approval_mode": "manual",
  "approved": true,
  "status": "success",
  "result_preview": "",
  "error": null,
  "created_at": "datetime",
  "duration_ms": 1000
}
```

---

## 12. Plugin Tools

Plugins podem registrar tools.

Manifesto exemplo:

```json
{
  "id": "plugin_github",
  "name": "GitHub Plugin",
  "version": "0.1.0",
  "tools": [
    {
      "name": "github.search_repos",
      "description": "Pesquisa repositórios no GitHub.",
      "capability": "github",
      "critical": false
    }
  ]
}
```

Regras:

* Plugins não podem sobrescrever core tools.
* Tools de plugins devem ter namespace próprio.
* Plugin tools devem passar pelo mesmo sistema de permissão.
* Plugin tools críticas devem pedir aprovação no modo manual.

---

## 13. MCP Tools

Tools vindas de MCP devem ser registradas dinamicamente.

Formato interno:

```txt
mcp.{server_id}.{tool_name}
```

Exemplo:

```txt
mcp.github.create_issue
```

Regras:

* MCP tools devem aparecer para agentes como tools comuns.
* Devem passar por permissões.
* Devem gerar auditoria.
* Devem respeitar approval mode.

---

## 14. API Inicial

### Listar capabilities

```txt
GET /api/tools/capabilities
```

### Listar tools

```txt
GET /api/tools
```

### Listar tools de um agente

```txt
GET /api/agents/{agent_id}/tools
```

### Atualizar tools/capabilities de agente

```txt
PUT /api/agents/{agent_id}/tools
```

### Criar workspace

```txt
POST /api/workspaces
```

### Listar workspaces

```txt
GET /api/workspaces
```

### Testar tool

```txt
POST /api/tools/test
```

---

## 15. Segurança

Implementar no MVP:

* Normalização de caminhos.
* Bloqueio de path traversal.
* Restrição por workspace.
* Timeout para terminal.
* Logs de todas as tools.
* Bloqueio de tool não autorizada.
* Mascaramento de segredos em logs.
* Modo auto aprovação explícito e visível.

---

## 16. Testes

Testes mínimos:

* Agent com capability filesystem_read consegue ler arquivo permitido.
* Agent sem filesystem_read não consegue ler.
* Agent não consegue acessar fora do workspace.
* Agent com terminal consegue executar comando.
* Agent sem terminal não consegue executar comando.
* Modo manual cria approval request.
* Modo auto executa direto.
* blocked_tools bloqueia mesmo com capability.
* Tool inexistente retorna erro.
* Logs são criados para todas as execuções.

---

## 17. Critérios de Aceite

O módulo estará pronto quando:

* Tools nativas forem registradas.
* Capabilities funcionarem.
* Agentes puderem receber tools/capabilities.
* Workspaces limitarem filesystem.
* Terminal tool funcionar.
* Aprovação manual pausar execução.
* Auto aprovação executar direto.
* Logs forem salvos.
* Plugin tools puderem ser registradas.
* MCP tools puderem ser registradas.
* O frontend conseguir listar e configurar tools por agente.
