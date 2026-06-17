# 02-agent-runtime.md

# AgentDesk — Agent Runtime Spec

## 1. Objetivo

O Agent Runtime é responsável por executar um agente individual.

Ele recebe configuração do agente, contexto da execução e mensagem de entrada, monta o prompt final, chama o modelo, interpreta respostas, dispara tools quando necessário e retorna eventos ao Core Orchestrator.

---

## 2. Responsabilidades

O Agent Runtime deve:

* Carregar configuração do agente.
* Montar contexto.
* Inserir memórias relevantes.
* Inserir skills ativas.
* Inserir tools disponíveis.
* Chamar o provider/modelo configurado.
* Interpretar respostas do modelo.
* Detectar chamadas de tools.
* Solicitar execução de tools ao orquestrador.
* Chamar subagentes quando permitido.
* Produzir resposta final.
* Emitir eventos estruturados.

---

## 3. Não Responsabilidades

O Agent Runtime não deve:

* Decidir sozinho permissões críticas.
* Executar tools diretamente sem passar pelo orquestrador.
* Salvar logs diretamente.
* Manipular UI.
* Implementar chamadas específicas de Ollama/OpenRouter sem usar Model Providers.
* Acessar banco diretamente, exceto por interfaces injetadas.

---

## 4. Agent Config

Estrutura inicial:

```json
{
  "id": "agent_001",
  "name": "Assistente Geral",
  "description": "Agente para tarefas gerais do dia a dia",
  "system_prompt": "Você é um assistente útil e organizado.",
  "provider": "ollama",
  "model": "qwen3:8b",
  "model_config": {
    "temperature": 0.4,
    "context_window": 8192,
    "top_p": 0.9,
    "max_tokens": 2048
  },
  "tools": [
    "filesystem.read",
    "filesystem.list",
    "memory.search"
  ],
  "skills": [],
  "mcp_servers": [],
  "memory": {
    "use_global": true,
    "use_agent_memory": true,
    "use_team_memory": false
  },
  "subagents": {
    "can_call": true,
    "allowed_agent_ids": ["*"]
  }
}
```

---

## 5. Runtime Input

```json
{
  "execution_id": "exec_001",
  "agent_id": "agent_001",
  "message": "Analise meus arquivos e encontre coisas grandes",
  "context": {
    "approval_mode": "manual",
    "workspace_ids": ["workspace_001"],
    "memory_scope": {
      "global": true,
      "agent_id": "agent_001",
      "team_id": null
    }
  }
}
```

---

## 6. Runtime Output

```json
{
  "status": "completed",
  "final_answer": "Encontrei os principais arquivos grandes...",
  "events": []
}
```

O runtime deve preferencialmente funcionar com streaming de eventos.

---

## 7. Montagem de Contexto

O prompt final deve ser montado em camadas:

1. System prompt base do AgentDesk.
2. System prompt do agente.
3. Regras do modo de aprovação.
4. Tools disponíveis.
5. Skills ativas.
6. Memórias relevantes.
7. Contexto do workspace.
8. Histórico recente da execução.
9. Mensagem atual do usuário.

Ordem sugerida:

```txt
[AGENTDESK SYSTEM RULES]

[AGENT SYSTEM PROMPT]

[OPERATION MODE]

[AVAILABLE TOOLS]

[ACTIVE SKILLS]

[RELEVANT MEMORIES]

[EXECUTION CONTEXT]

[USER REQUEST]
```

---

## 8. Regras Base do Runtime

Todo agente deve seguir regras base:

* Não fingir que executou uma ação.
* Usar tools quando precisar acessar dados reais.
* Respeitar tools disponíveis.
* Não usar tools não atribuídas ao agente.
* Não ocultar ações executadas.
* Registrar intenção de chamar subagente quando aplicável.
* Em modo manual, ações críticas dependem de aprovação.
* Em modo auto, ações são executadas sem confirmação.
* Retornar resposta final clara.

---

## 9. Tool Calling

O runtime deve usar um formato estruturado para tool calls.

Formato sugerido:

```json
{
  "type": "tool_call",
  "tool": "filesystem.list",
  "arguments": {
    "path": "C:/Users/Carlos/Documents"
  }
}
```

O runtime não executa a tool diretamente.

Ele envia a intenção ao Core Orchestrator.

O orquestrador valida permissões e executa via Tools System.

---

## 10. Subagent Calling

Formato sugerido:

```json
{
  "type": "subagent_call",
  "target_agent_id": "agent_researcher",
  "task": "Pesquise arquivos grandes dentro do workspace informado e retorne uma lista resumida."
}
```

Regras:

* O runtime deve verificar se o agente pode chamar subagentes.
* O Core Orchestrator deve validar limites de profundidade.
* O resultado do subagente deve voltar como contexto para o agente chamador.

---

## 11. Memória

Antes de chamar o modelo, o runtime deve solicitar memórias relevantes ao Memory System.

Escopos possíveis:

* Global.
* Agente.
* Time.

Exemplo:

```python
memory.search(
  query=user_message,
  scopes=["global", "agent:agent_001"]
)
```

O runtime também pode sugerir criação de memória.

Exemplo:

```json
{
  "type": "memory_write",
  "scope": "agent",
  "content": "O usuário prefere relatórios objetivos com tabelas.",
  "classification": "preference"
}
```

A memória deve ser criada pelo Memory System, não diretamente pelo runtime.

---

## 12. Skills

Skills devem ser injetadas no contexto do agente quando ativas.

Uma skill pode conter:

```json
{
  "id": "skill_report_writer",
  "name": "Escritor de Relatórios",
  "description": "Ajuda o agente a gerar relatórios claros.",
  "prompt": "Ao gerar relatórios, organize por resumo, achados, riscos e próximos passos."
}
```

O runtime deve carregar skills do agente e adicioná-las no prompt.

---

## 13. Erros

O runtime deve tratar:

* Provider indisponível.
* Modelo inexistente.
* Contexto maior que limite.
* Tool inválida.
* Tool negada.
* Subagente inexistente.
* Falha de parsing.
* Timeout.

Erro padrão:

```json
{
  "status": "failed",
  "error": {
    "code": "MODEL_UNAVAILABLE",
    "message": "O modelo configurado não está disponível no Ollama."
  }
}
```

---

## 14. Estratégia de Parsing Inicial

Para simplificar o MVP, o runtime deve aceitar duas formas de resposta do modelo:

### Resposta final

```json
{
  "type": "final_answer",
  "content": "Resposta final ao usuário."
}
```

### Ação

```json
{
  "type": "tool_call",
  "tool": "filesystem.read",
  "arguments": {
    "path": "..."
  }
}
```

Caso o modelo retorne texto comum, o runtime pode tratar como resposta final.

---

## 15. API Interna

Interface sugerida:

```python
class AgentRuntime:
    async def run(
        self,
        agent_config: AgentConfig,
        execution_context: ExecutionContext,
        message: str
    ) -> AgentRunResult:
        ...
```

Resultado:

```python
class AgentRunResult:
    status: str
    final_answer: str | None
    events: list[ExecutionEvent]
    error: RuntimeErrorData | None
```

---

## 16. Streaming

O runtime deve emitir eventos durante a execução.

Eventos mínimos:

```txt
agent_started
model_request_started
model_response_chunk
tool_call_requested
tool_result_received
subagent_call_requested
memory_context_loaded
agent_completed
agent_failed
```

---

## 17. Critérios de Aceite

O Agent Runtime estará pronto quando:

* Conseguir executar um agente com Ollama.
* Conseguir executar um agente com OpenRouter.
* Conseguir montar prompt com system prompt, tools, skills e memórias.
* Conseguir interpretar resposta final.
* Conseguir interpretar tool call.
* Conseguir solicitar tool ao orquestrador.
* Conseguir solicitar subagente.
* Conseguir emitir eventos.
* Conseguir tratar erros básicos.
* Funcionar sem depender do frontend.
