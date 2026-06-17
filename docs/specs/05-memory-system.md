# 05-memory-system.md

# AgentDesk — Memory System Spec

## 1. Objetivo

O Memory System é responsável por armazenar, classificar, recuperar e conectar memórias usadas pelos agentes.

O AgentDesk deve possuir um cérebro local unificado, com diferentes escopos:

* Memória global.
* Memória por agente.
* Memória por time.
* Futuramente memória por workspace/projeto.

O sistema deve usar armazenamento local em AppData, SQLite e embeddings locais via Ollama.

---

## 2. Responsabilidades

O módulo deve:

* Criar memórias.
* Atualizar memórias.
* Remover memórias.
* Classificar memórias.
* Gerar embeddings locais.
* Fazer busca semântica.
* Fazer busca textual.
* Separar memórias por escopo.
* Conectar memórias relacionadas.
* Retornar contexto relevante para agentes.
* Registrar origem das memórias.
* Permitir auditoria e edição pelo usuário.

---

## 3. Escopos de Memória

### Global

Disponível para todos os agentes.

Exemplos:

* Preferências do usuário.
* Perfil do usuário.
* Regras gerais.
* Projetos importantes.

### Agente

Disponível para um agente específico.

Exemplos:

* Preferências daquele agente.
* Histórico de decisões do agente.
* Especialização daquele agente.

### Time

Disponível para um time específico.

Exemplos:

* Estratégias do time.
* Histórico de tarefas do time.
* Decisões coletivas.

### Workspace

Não obrigatório no primeiro corte, mas recomendado para estrutura futura.

Exemplos:

* Contexto de projeto.
* Arquivos importantes.
* Convenções locais.

---

## 4. Tipos de Memória

Tipos iniciais:

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

Descrição:

### profile

Informações gerais úteis sobre o usuário.

### preference

Preferências de resposta, formato, ferramentas ou estilo.

### project

Informações sobre projetos.

### file_reference

Referências a arquivos/pastas importantes.

### task_history

Resumo de tarefas realizadas.

### decision

Decisões tomadas pelo usuário ou agentes.

### lesson

Aprendizados úteis para tarefas futuras.

### error_pattern

Erros recorrentes e soluções.

### workflow

Passos reutilizáveis para uma tarefa.

### system_note

Notas internas do sistema.

---

## 5. Estrutura da Memória

```json
{
  "id": "mem_001",
  "scope": "global | agent | team | workspace",
  "scope_id": null,
  "type": "preference",
  "title": "Preferência por respostas objetivas",
  "content": "O usuário prefere respostas diretas e práticas.",
  "tags": ["resposta", "estilo"],
  "source": {
    "type": "user_message | agent_observation | manual | imported",
    "execution_id": "exec_001",
    "agent_id": "agent_001"
  },
  "confidence": 0.9,
  "importance": 0.7,
  "created_at": "datetime",
  "updated_at": "datetime",
  "last_used_at": "datetime | null",
  "usage_count": 0
}
```

---

## 6. Embeddings

O sistema deve gerar embeddings localmente usando Ollama.

Modelo inicial sugerido:

```txt
nomic-embed-text
```

Configuração:

```json
{
  "embedding_provider": "ollama",
  "embedding_model": "nomic-embed-text",
  "base_url": "http://localhost:11434"
}
```

---

## 7. Armazenamento

Usar SQLite para metadados e vetores.

Tabelas iniciais:

```txt
memories
memory_embeddings
memory_links
memory_usage
```

### memories

```txt
id
scope
scope_id
type
title
content
tags_json
source_json
confidence
importance
created_at
updated_at
last_used_at
usage_count
deleted_at
```

### memory_embeddings

```txt
memory_id
embedding_model
embedding_vector
created_at
```

O vetor pode ser armazenado inicialmente como JSON ou BLOB.

### memory_links

```txt
id
source_memory_id
target_memory_id
relation_type
strength
created_at
```

### memory_usage

```txt
id
memory_id
execution_id
agent_id
used_at
```

---

## 8. Busca de Memória

O sistema deve suportar:

### Busca Semântica

Usa embeddings.

Entrada:

```json
{
  "query": "Como o usuário prefere relatórios?",
  "scopes": ["global", "agent:agent_001"],
  "limit": 8
}
```

Saída:

```json
[
  {
    "memory_id": "mem_001",
    "score": 0.87,
    "title": "Preferência por relatórios objetivos",
    "content": "O usuário prefere relatórios com resumo, achados e próximos passos."
  }
]
```

### Busca Textual

Busca por título, conteúdo e tags.

### Busca Híbrida

Combina semântica + textual.

Recomendação para MVP: busca híbrida simples.

---

## 9. Recuperação de Contexto para Agentes

Antes de cada execução, o Agent Runtime deve solicitar memórias relevantes.

Critérios:

* Similaridade com a solicitação.
* Escopo permitido.
* Importância.
* Confiança.
* Uso recente.
* Tipo de memória.

O retorno deve ser compacto para não estourar contexto.

Formato sugerido:

```txt
[Memória: preference | global]
O usuário prefere respostas objetivas.

[Memória: project | team]
O projeto AgentDesk usa Electron + FastAPI.
```

---

## 10. Criação Automática de Memórias

Agentes podem sugerir criação de memória.

Exemplo:

```json
{
  "type": "memory_create_request",
  "scope": "global",
  "memory_type": "preference",
  "title": "Prefere dashboard rico",
  "content": "O usuário prefere um dashboard rico, mas fácil de mexer.",
  "confidence": 0.85,
  "importance": 0.7
}
```

No modo manual:

* O sistema pode pedir aprovação para memórias importantes.

No modo auto:

* Pode criar diretamente.

Para o MVP, criação automática pode ser registrada e exibida para revisão futura.

---

## 11. Conexões entre Memórias

Memórias podem ser conectadas.

Tipos de relação:

```txt
related_to
contradicts
updates
supports
belongs_to_project
derived_from
```

Exemplo:

```json
{
  "source_memory_id": "mem_002",
  "target_memory_id": "mem_001",
  "relation_type": "updates",
  "strength": 0.9
}
```

---

## 12. Deduplicação

Antes de criar nova memória, o sistema deve buscar memórias semelhantes.

Se encontrar memória parecida:

* Atualizar a memória existente, ou
* Criar nova memória ligada por `related_to`.

No MVP, pode usar regra simples:

* Similaridade alta acima de 0.9 = possível duplicata.
* Similaridade entre 0.75 e 0.9 = memória relacionada.

---

## 13. Edição pelo Usuário

O frontend deve permitir:

* Ver memórias.
* Filtrar por escopo.
* Filtrar por tipo.
* Buscar memórias.
* Editar memória.
* Excluir memória.
* Ver origem.
* Ver uso.
* Ver memórias conectadas.

---

## 14. API Inicial

### Criar memória

```txt
POST /api/memories
```

### Listar memórias

```txt
GET /api/memories
```

Filtros:

```txt
scope
scope_id
type
tag
query
```

### Buscar memória

```txt
POST /api/memories/search
```

Body:

```json
{
  "query": "preferências de relatório",
  "scopes": ["global", "agent:agent_001"],
  "limit": 10
}
```

### Atualizar memória

```txt
PUT /api/memories/{memory_id}
```

### Deletar memória

```txt
DELETE /api/memories/{memory_id}
```

### Criar conexão

```txt
POST /api/memories/{memory_id}/links
```

---

## 15. Privacidade e Segurança

* Tudo deve ser armazenado localmente.
* Memórias não devem ser enviadas para OpenRouter sem necessidade.
* O usuário deve conseguir apagar memórias.
* O usuário deve conseguir desativar memória por agente.
* Memórias sensíveis devem poder ser marcadas como privadas.
* Logs devem indicar quando memórias foram usadas.

---

## 16. Testes

Testes mínimos:

* Criar memória global.
* Criar memória de agente.
* Criar memória de time.
* Gerar embedding via Ollama.
* Buscar memória por texto.
* Buscar memória por embedding.
* Buscar respeitando escopo.
* Não retornar memória de outro agente quando não permitido.
* Atualizar memória.
* Deletar memória.
* Criar link entre memórias.
* Deduplicação simples.

---

## 17. Critérios de Aceite

O Memory System estará pronto quando:

* Existirem memórias globais, de agente e de time.
* O sistema gerar embeddings locais.
* Busca semântica funcionar.
* Busca textual funcionar.
* Busca híbrida funcionar de forma básica.
* Agentes receberem memórias relevantes.
* Memórias puderem ser criadas/editadas/removidas.
* Memórias tiverem classificação.
* Memórias tiverem origem rastreável.
* Uso de memória aparecer nos logs.
* Tudo funcionar localmente no AppData.
