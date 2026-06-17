# 08-teams-agents.md

# AgentDesk — Teams of Agents Spec

## 1. Objetivo

Permitir que usuários criem times de agentes para trabalhar em conjunto.

Cada time possui um agente chefe responsável por planejar, delegar, revisar e consolidar respostas.

---

## 2. Conceitos

### Time

Grupo configurável de agentes.

### Agente Chefe

Agente responsável pela coordenação.

### Agente Membro

Agente especializado que executa tarefas delegadas.

### Timeline

Visualização dos eventos e mensagens operacionais entre agentes.

---

## 3. Estrutura de Time

```json
{
  "id": "team_001",
  "name": "Time de Pesquisa e Escrita",
  "description": "Pesquisa, analisa e escreve relatórios.",
  "leader_agent_id": "agent_leader",
  "member_agent_ids": [
    "agent_researcher",
    "agent_writer",
    "agent_reviewer"
  ],
  "execution_strategy": "leader_managed",
  "memory": {
    "use_global": true,
    "use_team_memory": true,
    "allow_member_memories": true
  },
  "tools_policy": {
    "inherit_from_agents": true
  }
}
```

---

## 4. Responsabilidades do Agente Chefe

O agente chefe deve:

* Interpretar a solicitação.
* Criar plano de trabalho.
* Escolher agentes membros.
* Delegar tarefas.
* Acompanhar resultados.
* Pedir novas iterações se necessário.
* Revisar qualidade.
* Consolidar resposta final.
* Registrar decisões importantes.

---

## 5. Estratégia de Execução do MVP

Estratégia inicial:

```txt
leader_managed
```

Fluxo:

1. Usuário envia tarefa ao time.
2. Líder cria plano.
3. Líder chama membros conforme necessário.
4. Membros retornam respostas.
5. Líder revisa.
6. Líder entrega resposta final.

Futuro:

```txt
parallel
sequential
debate
review_chain
```

---

## 6. Comunicação Visível

A timeline deve mostrar comunicação operacional, sem expor raciocínio interno privado.

Exemplos visíveis:

```txt
Líder: Vou dividir a tarefa entre pesquisa e escrita.
Pesquisador: Encontrei os principais pontos.
Redator: Preparei um rascunho.
Revisor: Sugeri ajustes.
Líder: Consolidei a resposta final.
```

---

## 7. Eventos de Time

Tipos:

```txt
team_started
leader_plan_created
member_assigned
member_started
member_completed
leader_review_started
leader_finalized
team_failed
```

Exemplo:

```json
{
  "type": "member_assigned",
  "team_id": "team_001",
  "leader_agent_id": "agent_leader",
  "member_agent_id": "agent_researcher",
  "task": "Pesquisar contexto relevante."
}
```

---

## 8. Memória de Time

Times possuem memória própria.

Usos:

* Estratégias que funcionaram.
* Preferências do time.
* Decisões recorrentes.
* Histórico de tarefas.
* Projetos recorrentes.

Escopos usados:

```txt
global
team:{team_id}
agent:{agent_id}
```

---

## 9. Tools em Times

Cada agente usa suas próprias tools.

O time pode definir política:

```json
{
  "inherit_from_agents": true,
  "additional_capabilities": [],
  "blocked_tools": []
}
```

Regras:

* `blocked_tools` do time vence.
* Tools críticas respeitam modo de aprovação.
* Auto aprovação executa sem confirmação.

---

## 10. Subagentes dentro de Times

Agentes membros também podem chamar subagentes se configurados.

O Core Orchestrator deve controlar:

* Profundidade máxima.
* Número máximo de chamadas.
* Eventos visíveis.
* Logs.

---

## 11. API Inicial

```txt
GET /api/teams
POST /api/teams
GET /api/teams/{team_id}
PUT /api/teams/{team_id}
DELETE /api/teams/{team_id}

POST /api/executions/team
```

---

## 12. Interface

Tela Times:

* Criar time.
* Editar time.
* Definir líder.
* Adicionar/remover agentes.
* Definir estratégia.
* Configurar memória.
* Configurar tools/capabilities.
* Executar tarefa.
* Ver timeline.

---

## 13. Critérios de Aceite

O módulo estará pronto quando:

* Usuário conseguir criar time.
* Usuário conseguir definir agente chefe.
* Usuário conseguir adicionar membros.
* Time conseguir executar tarefa.
* Líder conseguir delegar tarefas.
* Membros conseguirem responder.
* Líder conseguir consolidar resposta.
* Timeline mostrar comunicação operacional.
* Memória de time funcionar.
* Logs registrarem execução completa.
