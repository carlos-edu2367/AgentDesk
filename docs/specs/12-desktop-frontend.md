# 12-desktop-frontend.md

# AgentDesk — Desktop Frontend Spec

## 1. Objetivo

Definir a interface desktop do AgentDesk.

O frontend deve ser um app desktop rico, amigável e poderoso, construído com Electron, React, TypeScript, Vite e TailwindCSS.

O foco é permitir que o usuário configure agentes, times, modelos, tools, MCPs, skills, plugins, memórias, workspaces e acompanhe execuções em tempo real.

---

## 2. Stack

Frontend:

```txt
Electron
React
TypeScript
Vite
TailwindCSS
```

Backend local:

```txt
FastAPI embutido no Electron
```

Comunicação frontend/backend:

```txt
HTTP REST
SSE ou WebSocket para eventos em tempo real
```

Recomendação para MVP:

```txt
REST + SSE
```

---

## 3. Princípios de UX

O AgentDesk terá muitas funcionalidades. Por isso, a interface deve priorizar:

* Clareza.
* Organização visual.
* Dashboard rico, mas fácil de mexer.
* Navegação lateral fixa.
* Configurações progressivas.
* Estados vazios bem explicados.
* Logs sempre acessíveis.
* Aprovações visíveis.
* Execuções em tempo real.
* Evitar telas técnicas demais para usuário comum.
* Permitir profundidade para usuários avançados.

---

## 4. Estrutura Geral

Layout principal:

```txt
┌───────────────────────────────────────────┐
│ Top Bar                                   │
├───────────────┬───────────────────────────┤
│ Sidebar       │ Main Content              │
│               │                           │
│ Navigation    │ Tela atual                │
│               │                           │
└───────────────┴───────────────────────────┘
```

---

## 5. Navegação Principal

Sidebar:

```txt
Home
Agents
Teams
Executions
Memory
Workspaces
Tools
MCP Servers
Skills
Plugins
Providers
Settings
Audit Logs
```

---

## 6. Home / Dashboard

A tela inicial deve mostrar uma visão geral do sistema.

Componentes:

* Status do backend.
* Status do Ollama.
* Status do OpenRouter.
* Últimas execuções.
* Agentes recentes.
* Times recentes.
* Aprovações pendentes.
* Uso recente de tools.
* Atalhos para criar agente/time.
* Alertas importantes.

Cards sugeridos:

```txt
Model Providers
Agents
Teams
Pending Approvals
Recent Executions
Memory Status
MCP Servers
```

Ações rápidas:

```txt
Novo agente
Novo time
Nova execução
Cadastrar workspace
Configurar Ollama
Adicionar MCP
Criar skill
```

---

## 7. Agents

Tela para listar, criar, editar e executar agentes.

### Lista de Agentes

Cada card de agente deve mostrar:

* Nome.
* Descrição.
* Provider/modelo.
* Capabilities principais.
* Skills ativas.
* Status.
* Última execução.

Ações:

```txt
Abrir
Editar
Executar
Duplicar
Excluir
```

### Criar/Editar Agente

Campos:

```txt
Nome
Descrição
System Prompt
Provider
Modelo
Temperatura
Top P
Janela de contexto
Max tokens
Stream ligado/desligado
Capabilities
Tools explícitas
Tools bloqueadas
Skills
Plugins
MCP Servers
Memória
Subagentes
Workspaces permitidos
```

### Aba de Configuração de Modelo

Deve permitir:

* Escolher provider.
* Escolher modelo.
* Definir temperatura.
* Definir top_p.
* Definir context_window.
* Definir max_tokens.
* Testar modelo.

### Aba de Tools

Deve permitir:

* Marcar capabilities.
* Ver tools incluídas por capability.
* Adicionar tools específicas.
* Bloquear tools específicas.
* Ver risco de cada tool.

### Aba de Memória

Configurações:

```txt
Usar memória global
Usar memória do agente
Usar memória de time quando aplicável
Permitir criar memórias
Permitir buscar memórias
```

### Aba de Subagentes

Configurações:

```txt
Pode chamar subagentes
Pode chamar qualquer agente
Lista de agentes permitidos
Profundidade máxima
```

---

## 8. Teams

Tela para criar e gerenciar times de agentes.

### Lista de Times

Cada card deve mostrar:

* Nome.
* Descrição.
* Agente chefe.
* Quantidade de membros.
* Estratégia.
* Última execução.

### Criar/Editar Time

Campos:

```txt
Nome
Descrição
Agente chefe
Membros
Estratégia de execução
Memória do time
Workspaces permitidos
Policy de tools
```

Estratégia inicial:

```txt
leader_managed
```

Futuro:

```txt
parallel
sequential
debate
review_chain
```

### Execução de Time

Tela deve mostrar:

* Solicitação do usuário.
* Agente chefe.
* Membros acionados.
* Timeline.
* Aprovações.
* Resultado final.

---

## 9. Executions

Tela de histórico e execução em tempo real.

### Lista de Execuções

Filtros:

```txt
Data
Agente
Time
Status
Approval mode
Tool usada
Risco
```

Cada item mostra:

* Tipo.
* Agente/time.
* Status.
* Resumo.
* Data.
* Duração.

### Detalhe da Execução

Deve mostrar:

* Entrada do usuário.
* Resultado final.
* Timeline.
* Tools chamadas.
* Aprovações.
* Memórias usadas.
* Subagentes.
* Erros.
* Logs técnicos.
* Exportar JSON.

---

## 10. Timeline de Execução

A timeline é uma das telas mais importantes do AgentDesk.

Deve mostrar eventos em tempo real:

```txt
Usuário enviou solicitação
Agente iniciou
Memórias carregadas
Modelo respondeu
Tool solicitada
Aprovação solicitada
Tool executada
Subagente chamado
Membro do time respondeu
Execução concluída
```

Não deve mostrar raciocínio interno privado.

Deve mostrar comunicação operacional entre agentes.

Exemplo:

```txt
Líder: Vou dividir a tarefa entre pesquisa e escrita.
Pesquisador: Encontrei os principais pontos.
Redator: Preparei um rascunho.
Revisor: Sugeri melhorias.
Líder: Consolidei a resposta final.
```

---

## 11. Approvals

Aprovações devem aparecer:

* Na Home.
* Na execução atual.
* Em uma aba/painel lateral.

Cada aprovação mostra:

```txt
Agente
Tool
Resumo
Argumentos
Risco
Botão aprovar
Botão recusar
```

No modo auto aprovação, a UI deve mostrar claramente:

```txt
Auto approval ativo — ações serão executadas sem confirmação.
```

---

## 12. Memory

Tela para visualizar e editar memórias.

Funcionalidades:

* Listar memórias.
* Buscar memórias.
* Filtrar por escopo.
* Filtrar por tipo.
* Ver origem.
* Ver uso.
* Editar.
* Excluir.
* Criar manualmente.
* Ver memórias conectadas.

Filtros:

```txt
Global
Agent
Team
Workspace
Tipo
Tag
Importância
Confiança
```

Detalhe da memória:

```txt
Título
Conteúdo
Escopo
Tipo
Tags
Origem
Confiança
Importância
Último uso
Quantidade de usos
Links
```

---

## 13. Workspaces

Tela para gerenciar áreas do filesystem permitidas.

Funcionalidades:

* Criar workspace.
* Escolher pasta.
* Definir permissões.
* Associar agentes.
* Associar times.
* Ver uso recente.

Permissões:

```txt
Read
Write
Delete
Execute
```

A UI deve deixar claro que workspaces controlam acesso real ao computador.

---

## 14. Tools

Tela para visualizar tools e capabilities.

Abas:

```txt
Capabilities
Core Tools
Plugin Tools
MCP Tools
```

Cada tool deve mostrar:

* Nome.
* Descrição.
* Source.
* Capability.
* Critical.
* Input schema.
* Agentes que podem usar.

---

## 15. MCP Servers

Tela para configurar servidores MCP manualmente.

Funcionalidades:

* Criar MCP.
* Editar.
* Remover.
* Ativar/desativar.
* Testar conexão.
* Ver tools detectadas.
* Associar a agentes.
* Associar a times.

Campos:

```txt
Nome
ID
Transport
Command
Args
Env
Enabled
```

MVP:

```txt
stdio
```

---

## 16. Skills

Tela para criar e gerenciar skills.

Funcionalidades:

* Criar skill.
* Editar skill.
* Excluir skill.
* Importar JSON.
* Exportar JSON.
* Associar a agente.
* Associar a time.

Campos:

```txt
Nome
Descrição
Versão
Tags
Prompt
Exemplos
```

---

## 17. Plugins

Tela para plugins locais.

Funcionalidades:

* Importar plugin por pasta.
* Criar plugin básico.
* Ativar/desativar.
* Ver manifesto.
* Ver tools.
* Ver skills.
* Ver permissões.
* Ver logs de uso.

A interface deve avisar que plugins podem executar código.

---

## 18. Providers

Tela de configuração de providers.

### Ollama

Campos:

```txt
Base URL
Testar conexão
Listar modelos
Modelo de embedding
```

### OpenRouter

Campos:

```txt
Base URL
API Key
Testar conexão
Listar modelos
```

API key deve ser mascarada.

---

## 19. Settings

Configurações gerais:

```txt
Tema
Idioma
Default approval mode
Retenção de logs
Pasta AppData
Limpeza de temp
Backup
Restore
Telemetria desligada por padrão
```

---

## 20. Estados Vazios

Toda tela deve ter estado vazio útil.

Exemplo em Agents:

```txt
Nenhum agente criado ainda.
Crie seu primeiro agente para começar a automatizar tarefas.
[ Criar agente ]
```

---

## 21. Design Visual

Direção sugerida:

* Dashboard moderno.
* Sidebar escura ou neutra.
* Cards limpos.
* Tipografia legível.
* Badges de status.
* Badges de risco.
* Timeline com blocos claros.
* Configurações em abas.
* Painéis laterais para detalhes.

Não precisa copiar ChatGPT, Cursor ou Notion, mas pode combinar:

* Dashboard de SaaS.
* Console de execução.
* Gerenciador de agentes.
* Área de configuração avançada.

---

## 22. Comunicação com Backend

REST para CRUD:

```txt
/api/agents
/api/teams
/api/executions
/api/memories
/api/workspaces
/api/tools
/api/mcp
/api/skills
/api/plugins
/api/providers
/api/settings
```

SSE para eventos:

```txt
/api/executions/{execution_id}/events
```

---

## 23. Critérios de Aceite

O frontend estará pronto quando:

* Usuário conseguir configurar providers.
* Usuário conseguir criar agentes.
* Usuário conseguir criar times.
* Usuário conseguir executar agente.
* Usuário conseguir executar time.
* Timeline mostrar eventos em tempo real.
* Aprovações funcionarem.
* Workspaces puderem ser criados.
* Memórias puderem ser visualizadas/editadas.
* MCPs puderem ser configurados.
* Skills puderem ser criadas.
* Plugins puderem ser importados.
* Logs puderem ser consultados.
* App parecer um desktop app completo, não apenas uma página web.
