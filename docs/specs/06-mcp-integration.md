# 06-mcp-integration.md

# AgentDesk — MCP Integration Spec

## 1. Objetivo

Permitir que o AgentDesk conecte servidores MCP configurados manualmente pelo usuário e exponha suas ferramentas para agentes e times.

Para o agente, tools MCP devem aparecer como tools comuns.

---

## 2. Responsabilidades

O módulo deve:

* Cadastrar servidores MCP.
* Testar conexão.
* Listar tools disponíveis.
* Ativar/desativar MCP por agente/time.
* Expor tools MCP ao Tool Registry.
* Executar chamadas MCP via Tools System.
* Registrar auditoria.
* Exibir erros claramente no frontend.

---

## 3. Configuração de MCP

Arquivo:

```txt
%APPDATA%/AgentDesk/config/mcp.config.json
```

Exemplo:

```json
{
  "servers": [
    {
      "id": "filesystem_mcp",
      "name": "Filesystem MCP",
      "enabled": true,
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Projetos"],
      "env": {}
    }
  ]
}
```

---

## 4. Tipos de Transporte

MVP obrigatório:

```txt
stdio
```

Futuro:

```txt
http
sse
websocket
```

---

## 5. Namespace Interno

Toda tool MCP deve ser registrada assim:

```txt
mcp.{server_id}.{tool_name}
```

Exemplo:

```txt
mcp.github.create_issue
mcp.filesystem.read_file
```

---

## 6. Interface no Frontend

Tela MCP deve permitir:

* Criar servidor.
* Editar servidor.
* Remover servidor.
* Ativar/desativar.
* Testar conexão.
* Ver tools detectadas.
* Copiar configuração JSON.
* Associar MCP a agentes/times.

---

## 7. Fluxo de Uso

1. Usuário cadastra servidor MCP.
2. Sistema testa conexão.
3. Sistema lista tools disponíveis.
4. Usuário habilita MCP em agente/time.
5. Agent Runtime recebe tools MCP no contexto.
6. Agente solicita chamada.
7. Tools System valida permissões.
8. MCP Client executa.
9. Resultado volta ao agente.
10. Auditoria registra tudo.

---

## 8. Estrutura de Tool MCP

```json
{
  "name": "mcp.github.create_issue",
  "description": "Cria uma issue no GitHub.",
  "server_id": "github",
  "original_tool_name": "create_issue",
  "input_schema": {},
  "critical": true
}
```

---

## 9. Permissões

MCP tools devem passar pelo mesmo sistema de permissões.

Capabilities sugeridas:

```txt
mcp
mcp.github
mcp.filesystem
```

No modo manual, chamadas MCP críticas devem pedir aprovação.

No modo auto, devem executar direto.

---

## 10. Auditoria

Registrar:

* Servidor MCP usado.
* Tool chamada.
* Argumentos.
* Resultado resumido.
* Erros.
* Agente responsável.
* Execução relacionada.

---

## 11. Erros

Códigos iniciais:

```txt
MCP_SERVER_NOT_FOUND
MCP_SERVER_DISABLED
MCP_CONNECTION_FAILED
MCP_TOOL_NOT_FOUND
MCP_TOOL_EXECUTION_FAILED
MCP_TIMEOUT
```

---

## 12. Critérios de Aceite

O módulo estará pronto quando:

* Usuário conseguir cadastrar MCP por interface.
* Sistema conseguir testar conexão stdio.
* Tools MCP aparecerem no Tool Registry.
* Agentes conseguirem usar tools MCP autorizadas.
* Execuções MCP gerarem logs.
* MCP puder ser habilitado/desabilitado por agente/time.
