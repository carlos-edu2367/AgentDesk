# 11-execution-logs-audit.md

# AgentDesk — Execution Logs & Audit Spec

## 1. Objetivo

Definir como o AgentDesk registra execuções, eventos, ações, aprovações, uso de tools, uso de memória e erros.

Logs e auditoria são parte central do produto, porque agentes podem executar ações reais no computador do usuário.

---

## 2. Tipos de Registro

O sistema deve manter três camadas:

```txt
Execution Log
Execution Event
Audit Log
```

---

## 3. Execution Log

Registro geral de uma execução.

```json
{
  "id": "exec_001",
  "type": "agent",
  "target_id": "agent_001",
  "user_input": "Organize meus arquivos.",
  "status": "completed",
  "approval_mode": "manual",
  "started_at": "datetime",
  "completed_at": "datetime",
  "result_preview": "Foram encontrados arquivos grandes...",
  "error": null
}
```

Objetivo:

* Mostrar histórico de execuções.
* Permitir abrir detalhes.
* Permitir retomar contexto.
* Permitir auditoria.

---

## 4. Execution Event

Evento granular de uma execução.

Exemplos:

```txt
agent_started
model_request_started
model_chunk
tool_call_requested
tool_executed
approval_requested
approval_resolved
memory_searched
memory_created
subagent_called
team_member_started
team_member_completed
execution_completed
execution_failed
```

Formato:

```json
{
  "id": "event_001",
  "execution_id": "exec_001",
  "type": "tool_call_requested",
  "source": "agent",
  "source_id": "agent_file_manager",
  "content": {
    "tool": "filesystem.list",
    "arguments": {
      "path": "C:/Projetos"
    }
  },
  "created_at": "datetime"
}
```

---

## 5. Audit Log

Registro de ações sensíveis ou relevantes.

Formato:

```json
{
  "id": "audit_001",
  "execution_id": "exec_001",
  "agent_id": "agent_file_manager",
  "event_type": "tool_executed",
  "risk_level": "medium",
  "summary": "Leu diretório do workspace Projetos.",
  "data": {},
  "created_at": "datetime"
}
```

---

## 6. O que Deve Gerar Audit Log

Obrigatório:

* Execução iniciada.
* Execução finalizada.
* Execução falhou.
* Tool executada.
* Tool negada.
* Aprovação solicitada.
* Aprovação concedida.
* Aprovação recusada.
* Terminal executado.
* Arquivo criado.
* Arquivo editado.
* Arquivo deletado.
* Requisição HTTP feita.
* Plugin instalado.
* MCP chamado.
* Memória criada.
* Memória deletada.
* API key configurada ou alterada, sem registrar valor.

---

## 7. Risk Level

Níveis:

```txt
low
medium
high
critical
```

Sugestão inicial:

```txt
filesystem.read       low
filesystem.write      medium
filesystem.delete     high
terminal.exec         high
http.request          medium
plugin.install        high
memory.delete         medium
mcp.call              medium/high
```

---

## 8. Mascaramento de Segredos

Logs nunca devem armazenar:

* API keys completas.
* Tokens.
* Senhas.
* Headers Authorization.
* Cookies.
* Chaves privadas.

Função obrigatória:

```python
mask_secrets(data)
```

Exemplo:

```txt
sk-or-v1-abc123456789 → sk-or-v1-***6789
```

---

## 9. Retenção

Configuração inicial:

```json
{
  "logs_retention_days": 90,
  "audit_retention_days": 365,
  "keep_failed_executions": true
}
```

No MVP, retenção automática pode ser opcional, mas a estrutura deve existir.

---

## 10. Timeline do Frontend

A timeline deve usar `ExecutionEvent`.

Deve mostrar:

* Mensagem do usuário.
* Agente iniciado.
* Modelo usado.
* Memórias usadas.
* Tools chamadas.
* Aprovações pendentes.
* Resultados de tools.
* Chamadas de subagentes.
* Comunicação entre agentes.
* Resultado final.

Não deve mostrar raciocínio interno privado.

---

## 11. Logs de Terminal

Para `terminal.exec`, registrar:

```json
{
  "command": "npm install",
  "cwd": "C:/Projetos/app",
  "exit_code": 0,
  "stdout_preview": "...",
  "stderr_preview": "...",
  "duration_ms": 10000
}
```

Regras:

* stdout/stderr grandes devem ser truncados.
* O usuário pode abrir log completo se disponível.
* Comando completo sempre deve aparecer.

---

## 12. Logs de Tools

Toda tool deve registrar:

```json
{
  "tool": "filesystem.write",
  "arguments": {},
  "status": "success",
  "duration_ms": 200,
  "result_preview": "",
  "error": null
}
```

---

## 13. Logs de Memória

Quando memória for usada:

```json
{
  "memory_id": "mem_001",
  "scope": "global",
  "type": "preference",
  "score": 0.87
}
```

Quando memória for criada:

```json
{
  "memory_id": "mem_002",
  "scope": "agent",
  "type": "lesson",
  "title": "Como organizar arquivos grandes"
}
```

---

## 14. API Inicial

```txt
GET /api/executions
GET /api/executions/{execution_id}
GET /api/executions/{execution_id}/events
GET /api/audit
GET /api/audit/{audit_id}
POST /api/logs/cleanup
```

Filtros úteis:

```txt
date_from
date_to
agent_id
team_id
status
risk_level
tool
event_type
```

---

## 15. Exportação de Logs

O sistema deve permitir exportar logs de uma execução.

Formatos futuros:

```txt
json
md
html
```

No MVP, exportar JSON já basta.

---

## 16. Critérios de Aceite

Esta spec estará cumprida quando:

* Toda execução gerar registro.
* Eventos aparecerem em tempo real.
* Timeline conseguir ler eventos.
* Toda tool gerar log.
* Toda ação crítica gerar audit log.
* Terminal gerar logs detalhados.
* Segredos forem mascarados.
* Logs puderem ser filtrados.
* Execuções puderem ser abertas depois.
* Logs puderem ser exportados em JSON.
