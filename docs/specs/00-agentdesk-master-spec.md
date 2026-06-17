# 00-agentdesk-master-spec.md

# AgentDesk — Master Spec

## 1. Visão Geral

O AgentDesk é um sistema desktop multiagêntico, open-source, Windows-first, criado para permitir que usuários configurem e executem agentes de IA para tarefas do dia a dia.

O sistema não é focado exclusivamente em código, mas deve permitir a criação de agentes especializados em programação quando o usuário desejar.

O AgentDesk deve suportar:

* Modelos locais via Ollama.
* Modelos remotos via OpenRouter.
* Configuração de modelo por agente.
* Criação de agentes e subagentes.
* Criação de times de agentes com agente chefe.
* Ferramentas configuráveis por agente.
* Conexão com servidores MCP.
* Sistema de skills e plugins.
* Memória global, por time e por agente.
* Execução com aprovação manual ou auto aprovação total.
* Interface desktop rica, amigável e auditável.

---

## 2. Stack Técnica Inicial

### Frontend Desktop

* Electron
* React
* TypeScript
* Vite
* TailwindCSS

### Backend Local Embutido

* Python
* FastAPI
* Uvicorn
* SQLite
* Arquivos JSON/Markdown
* AppData para armazenamento local no Windows

### IA / Model Providers

* Ollama para modelos locais.
* OpenRouter para modelos remotos.

### Embeddings

* Ollama embeddings.
* Modelo sugerido inicial: `nomic-embed-text`.

---

## 3. Sistema de Armazenamento Local

O sistema deve armazenar dados locais em:

```txt
%APPDATA%/AgentDesk/
```

Estrutura inicial sugerida:

```txt
AgentDesk/
  config/
    app.config.json
    providers.config.json
    permissions.config.json

  database/
    agentdesk.sqlite

  memories/
    global/
    agents/
    teams/

  skills/
    installed/
    custom/

  plugins/
    installed/
    custom/

  logs/
    executions/
    audit/

  workspaces/
    registry.json
```

---

## 4. Módulos Principais

### 4.1 Core Orchestrator

Responsável por coordenar execuções, agentes, times, subagentes, permissões, eventos e estado da tarefa.

Spec própria:

```txt
01-core-orchestrator.md
```

### 4.2 Agent Runtime

Responsável por executar agentes individuais, montar contexto, chamar modelo, interpretar tool calls e retornar eventos.

Spec própria:

```txt
02-agent-runtime.md
```

### 4.3 Model Providers

Responsável por abstrair Ollama e OpenRouter.

Spec própria futura:

```txt
03-model-providers.md
```

### 4.4 Tools & Permissions

Responsável por ferramentas disponíveis, permissões, aprovação manual e auto aprovação.

Spec própria futura:

```txt
04-tools-permissions.md
```

### 4.5 Memory System

Responsável por memória global, de agente, de time, embeddings, busca semântica e classificação.

Spec própria futura:

```txt
05-memory-system.md
```

### 4.6 MCP Integration

Responsável por cadastrar, testar, ativar e expor servidores MCP para agentes.

Spec própria futura:

```txt
06-mcp-integration.md
```

### 4.7 Skills & Plugins

Responsável por criação, instalação, importação e uso de skills/plugins locais.

Spec própria futura:

```txt
07-skills-plugins.md
```

### 4.8 Teams of Agents

Responsável por times, agente chefe, agentes subordinados e comunicação visível entre eles.

Spec própria futura:

```txt
08-teams-agents.md
```

### 4.9 Desktop Frontend

Responsável por dashboard, telas de agentes, times, execuções, memória, configurações e logs.

Spec própria futura:

```txt
09-desktop-frontend.md
```

---

## 5. Conceitos Fundamentais

### Agente

Um agente é uma entidade configurável com:

* Nome.
* Descrição.
* System prompt.
* Modelo.
* Provider.
* Temperatura.
* Janela de contexto.
* Tools habilitadas.
* MCPs habilitados.
* Skills habilitadas.
* Memória própria.
* Permissões.
* Capacidade de chamar subagentes.

### Subagente

Um subagente é um agente chamado por outro agente durante uma execução.

O agente principal pode delegar tarefas para subagentes livremente.

### Time de Agentes

Um time possui:

* Nome.
* Descrição.
* Agente chefe.
* Lista de agentes membros.
* Estratégia de execução.
* Memória própria.
* Logs próprios.

O usuário envia uma solicitação ao time, e o agente chefe coordena o trabalho.

### Agente Chefe

Responsável por:

* Entender a solicitação.
* Dividir tarefas.
* Acionar agentes.
* Revisar respostas.
* Consolidar resultado final.
* Registrar decisões.

### Tool

Uma ferramenta executável pelo agente.

Exemplos:

* Ler arquivos.
* Listar diretórios.
* Criar arquivos.
* Editar arquivos.
* Executar comandos.
* Usar MCP.
* Buscar memória.
* Criar memória.

### Skill

Uma skill é uma unidade reutilizável de comportamento.

Pode conter:

* Prompt.
* Template.
* Instruções.
* Workflow simples.
* Exemplos.

### Plugin

Um plugin é um pacote maior que pode conter:

* Skills.
* Tools.
* Configurações.
* Templates.
* Manifesto.
* Dependências.

---

## 6. Modos de Operação

### Modo Aguardar Aprovação

Ações críticas devem ser apresentadas ao usuário antes de execução.

Exemplos:

* Deletar arquivos.
* Editar arquivos.
* Executar comandos.
* Enviar requisições externas.
* Usar API paga.
* Instalar plugins.

### Modo Auto Aprovação

O agente tem liberdade total.

Nesse modo, nenhuma ação deve exigir confirmação.

Mesmo assim, tudo deve ser registrado nos logs de auditoria.

---

## 7. Workspaces e Acesso a Arquivos

O sistema não deve assumir acesso total ao filesystem por padrão.

O usuário deve poder cadastrar workspaces/pastas permitidas.

Cada workspace deve ter:

* Nome.
* Caminho.
* Permissões.
* Agentes autorizados.
* Times autorizados.

Exemplo:

```json
{
  "id": "workspace_001",
  "name": "Projetos",
  "path": "C:/Users/Carlos/Documents/Projetos",
  "permissions": {
    "read": true,
    "write": true,
    "delete": false,
    "execute": false
  }
}
```

---

## 8. Requisitos de Auditoria

Toda execução deve gerar logs.

Cada log deve conter:

* ID da execução.
* Data/hora.
* Usuário.
* Agente/time.
* Modelo usado.
* Provider usado.
* Mensagens trocadas.
* Tools chamadas.
* Aprovações solicitadas.
* Ações executadas.
* Erros.
* Resultado final.

---

## 9. MVP

O MVP deve conter:

* App desktop funcional no Windows.
* Backend FastAPI embutido.
* Cadastro de providers Ollama/OpenRouter.
* Criação de agentes.
* Configuração de modelo por agente.
* Configuração de tools por agente.
* Execução de agente individual.
* Criação de times.
* Execução de time com agente chefe.
* Subagentes.
* Timeline visível da execução.
* Memória global, por agente e por time.
* Embeddings locais via Ollama.
* Cadastro manual de MCP.
* Sistema inicial de skills/plugins locais.
* Modos aprovação/manual e auto aprovação.
* Logs/auditoria.

---

## 10. Princípios de Desenvolvimento

* Modularidade acima de velocidade.
* Cada módulo deve ter contrato claro.
* Evitar acoplamento forte entre frontend e lógica de agentes.
* O core deve funcionar mesmo sem frontend.
* O frontend deve consumir eventos do backend.
* Logs devem ser tratados como parte central do produto.
* Segurança deve ser configurável, não fixa.
* O sistema deve ser expansível para Linux/macOS no futuro.
* O projeto deve ser compreensível para contribuidores open-source.

---

## 11. Critérios de Aceite Gerais

O MVP será considerado funcional quando:

* O usuário conseguir iniciar o AgentDesk no Windows.
* O backend local iniciar junto com o Electron.
* O usuário conseguir cadastrar/configurar Ollama e OpenRouter.
* O usuário conseguir criar um agente.
* O usuário conseguir selecionar modelo por agente.
* O usuário conseguir conversar com um agente.
* O agente conseguir usar tools permitidas.
* O usuário conseguir criar um time.
* O agente chefe conseguir delegar tarefas.
* A timeline mostrar eventos de execução.
* A memória funcionar com busca semântica.
* MCPs puderem ser cadastrados manualmente.
* Skills/plugins locais puderem ser instalados/criados.
* Logs de auditoria forem salvos localmente.
