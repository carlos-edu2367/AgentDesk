# 10-local-storage.md

# AgentDesk — Local Storage Spec

## 1. Objetivo

Definir como o AgentDesk armazena dados localmente no Windows.

O sistema deve ser local-first, usando AppData, SQLite e arquivos estruturados.

---

## 2. Diretório Base

No Windows, todos os dados do AgentDesk devem ficar em:

```txt
%APPDATA%/AgentDesk/
```

Exemplo real:

```txt
C:/Users/{User}/AppData/Roaming/AgentDesk/
```

---

## 3. Estrutura de Diretórios

```txt
AgentDesk/
  config/
    app.config.json
    providers.config.json
    mcp.config.json
    permissions.config.json

  database/
    agentdesk.sqlite
    migrations/

  memories/
    global/
    agents/
    teams/
    workspaces/

  skills/
    installed/
    custom/

  plugins/
    installed/
    custom/

  logs/
    executions/
    audit/

  exports/
    reports/
    backups/

  temp/
    executions/
    downloads/

  workspaces/
    registry.json
```

---

## 4. SQLite

Banco principal:

```txt
%APPDATA%/AgentDesk/database/agentdesk.sqlite
```

Responsável por armazenar:

* Agents.
* Teams.
* Executions.
* Execution events.
* Memories.
* Embeddings.
* Workspaces.
* Skills.
* Plugins.
* MCP servers.
* Providers.
* Audit logs.
* Approvals.

---

## 5. Tabelas Iniciais

```txt
users
providers
agents
teams
team_agents
workspaces
agent_workspaces
team_workspaces

tools
capabilities
agent_tools
agent_capabilities

skills
agent_skills
plugins
agent_plugins

mcp_servers
agent_mcp_servers

executions
execution_events
approval_requests
audit_logs

memories
memory_embeddings
memory_links
memory_usage
```

---

## 6. Arquivos JSON de Configuração

### app.config.json

```json
{
  "app_name": "AgentDesk",
  "version": "0.1.0",
  "theme": "system",
  "default_approval_mode": "manual",
  "default_workspace_policy": "user_selected",
  "telemetry": false
}
```

### providers.config.json

```json
{
  "providers": [],
  "embedding_provider": {
    "type": "ollama",
    "model": "nomic-embed-text",
    "base_url": "http://localhost:11434"
  }
}
```

### mcp.config.json

```json
{
  "servers": []
}
```

### permissions.config.json

```json
{
  "default_capabilities": [],
  "critical_tools": [
    "filesystem.write",
    "filesystem.delete",
    "filesystem.move",
    "terminal.exec",
    "http.request",
    "memory.delete",
    "plugin.install",
    "mcp.call"
  ]
}
```

---

## 7. O que vai para SQLite vs Arquivo

### SQLite

Usar para dados consultáveis e relacionais:

* Agentes.
* Times.
* Execuções.
* Eventos.
* Memórias.
* Logs.
* Skills registradas.
* Plugins registrados.
* Workspaces.
* Providers.

### Arquivos

Usar para dados grandes, editáveis ou portáveis:

* Manifestos de plugins.
* Skills importadas.
* Exports.
* Backups.
* Logs extensos.
* Artefatos de execução.
* Arquivos temporários.

---

## 8. Migrations

O backend deve ter um sistema simples de migrações.

Pasta:

```txt
database/migrations/
```

Tabela:

```txt
schema_migrations
```

Campos:

```txt
id
version
name
applied_at
```

Regras:

* Migrations devem rodar ao iniciar o backend.
* Nunca apagar dados sem backup.
* Toda mudança de schema deve ter migration.

---

## 9. Backups

O MVP deve permitir backup manual.

Backup deve incluir:

* Banco SQLite.
* Configurações JSON.
* Skills customizadas.
* Plugins customizados.
* Memórias.
* Logs opcionais.

Formato sugerido:

```txt
AgentDesk-backup-YYYY-MM-DD-HH-mm.zip
```

Local padrão:

```txt
%APPDATA%/AgentDesk/exports/backups/
```

---

## 10. Exportação e Importação

Funcionalidades futuras, mas estrutura deve prever:

* Exportar agente.
* Importar agente.
* Exportar time.
* Importar time.
* Exportar skill.
* Importar skill.
* Exportar plugin.
* Importar plugin.
* Exportar memórias selecionadas.

---

## 11. Temp

Pasta:

```txt
temp/
```

Usada para:

* Execuções em andamento.
* Downloads temporários.
* Arquivos intermediários.
* Resultados parciais.

Regras:

* Arquivos temporários antigos podem ser limpos.
* Nunca salvar segredos permanentes em temp.
* Execuções devem ter subpasta por `execution_id`.

---

## 12. Segurança Local

Regras mínimas:

* API keys não devem aparecer em logs.
* Caminhos devem ser normalizados.
* Workspaces devem limitar filesystem.
* Plugins devem ficar em pastas próprias.
* Backups não devem ser enviados automaticamente para lugar nenhum.
* Tudo deve funcionar offline, exceto OpenRouter e integrações externas.

---

## 13. API Inicial de Storage/Backup

```txt
GET /api/storage/info
POST /api/storage/backup
GET /api/storage/backups
POST /api/storage/restore
POST /api/storage/cleanup-temp
```

---

## 14. Critérios de Aceite

Esta spec estará cumprida quando:

* O app criar a estrutura em AppData.
* O SQLite for criado automaticamente.
* Migrations rodarem no startup.
* Configs JSON forem criadas com defaults.
* Backups puderem ser gerados.
* O sistema distinguir corretamente SQLite e arquivos.
* Nenhuma API key aparecer em logs.
* O app funcionar offline com Ollama.
