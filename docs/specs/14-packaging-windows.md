# 14-packaging-windows.md

# AgentDesk — Windows Packaging Spec

## 1. Objetivo

Definir como empacotar, distribuir e executar o AgentDesk no Windows.

O MVP é Windows-first e deve funcionar como aplicativo desktop comum.

---

## 2. Stack de Packaging

Frontend:

```txt
Electron
electron-builder
```

Backend:

```txt
FastAPI
Uvicorn
Python embutido ou empacotado
```

Banco/local:

```txt
SQLite
AppData
```

---

## 3. Formatos de Distribuição

MVP recomendado:

```txt
NSIS installer
Portable build
```

### Installer

Arquivo:

```txt
AgentDesk-Setup-0.1.0.exe
```

### Portable

Arquivo:

```txt
AgentDesk-Portable-0.1.0.zip
```

---

## 4. Inicialização do App

Fluxo:

1. Usuário abre AgentDesk.
2. Electron inicia.
3. Electron verifica estrutura AppData.
4. Electron inicia backend FastAPI embutido.
5. Frontend verifica health check.
6. UI carrega dashboard.

---

## 5. Backend Embutido

O backend deve iniciar automaticamente junto com o Electron.

Opções:

```txt
Python empacotado com PyInstaller
Python incluído no instalador
```

Recomendação MVP:

```txt
Backend FastAPI empacotado com PyInstaller
```

Executável:

```txt
agentdesk-backend.exe
```

Electron executa:

```txt
resources/backend/agentdesk-backend.exe
```

---

## 6. Porta Local

Backend deve usar porta local.

Sugestão:

```txt
127.0.0.1:8765
```

Regras:

* Usar localhost apenas.
* Não expor para rede externa.
* Se porta estiver ocupada, tentar porta alternativa.
* Frontend deve descobrir porta ativa.
* Salvar porta em runtime config temporário.

---

## 7. Health Check

Endpoint obrigatório:

```txt
GET /api/health
```

Resposta:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "storage_ready": true,
  "database_ready": true
}
```

---

## 8. AppData

Ao iniciar, o app deve garantir:

```txt
%APPDATA%/AgentDesk/
```

E criar:

```txt
config/
database/
logs/
skills/
plugins/
memories/
exports/
temp/
workspaces/
```

---

## 9. Ollama

O AgentDesk não precisa instalar Ollama no MVP.

Mas deve:

* Detectar se Ollama está rodando.
* Mostrar status.
* Permitir configurar base URL.
* Mostrar instrução amigável se Ollama não estiver disponível.
* Permitir usar OpenRouter mesmo sem Ollama, exceto embeddings locais.

---

## 10. OpenRouter

OpenRouter deve funcionar se o usuário configurar API key.

Regras:

* API key salva localmente.
* API key mascarada na UI.
* API key nunca aparece em logs.

---

## 11. Atualizações

Auto update fica fora do MVP.

Mas a arquitetura deve prever:

```txt
Versão do app
Versão do schema
Versão dos plugins
Compatibilidade de specs
```

---

## 12. Logs do App

Logs técnicos do app:

```txt
%APPDATA%/AgentDesk/logs/app/
```

Devem incluir:

* Startup.
* Backend startup.
* Erros fatais.
* Falha de porta.
* Falha de database.
* Falha de migrations.

---

## 13. Fechamento do App

Ao fechar:

* Encerrar backend.
* Encerrar subprocessos controlados.
* Fechar SSE/WebSocket.
* Liberar locks.
* Finalizar execuções ou marcar como interrompidas.

Se houver execução ativa, a UI deve avisar:

```txt
Existem execuções em andamento. Deseja encerrar mesmo assim?
```

No modo auto aprovação, esse aviso ainda deve existir.

---

## 14. Build Scripts

Scripts sugeridos:

```json
{
  "scripts": {
    "dev": "concurrently \"npm:dev:frontend\" \"npm:dev:backend\"",
    "dev:frontend": "vite",
    "dev:electron": "electron .",
    "build:frontend": "vite build",
    "build:backend": "pyinstaller backend.spec",
    "build:electron": "electron-builder",
    "build:windows": "npm run build:frontend && npm run build:backend && npm run build:electron"
  }
}
```

---

## 15. Estrutura de Release

```txt
release/
  AgentDesk-Setup-0.1.0.exe
  AgentDesk-Portable-0.1.0.zip
  checksums.txt
```

---

## 16. Critérios de Aceite

Packaging estará pronto quando:

* App instalar no Windows.
* App abrir como desktop app.
* Backend iniciar automaticamente.
* Frontend conectar no backend.
* AppData for criado.
* SQLite for criado.
* Health check funcionar.
* Ollama for detectado se estiver rodando.
* App fechar backend corretamente.
* Build portable funcionar.
* Installer funcionar.

# 15-testing-strategy.md

# AgentDesk — Testing Strategy Spec

## 1. Objetivo

Definir a estratégia de testes do AgentDesk.

Como o sistema executa agentes com acesso a arquivos, terminal, plugins e MCP, testes são essenciais para evitar regressões e ações perigosas.

---

## 2. Camadas de Teste

O projeto deve ter:

```txt
Unit tests
Integration tests
End-to-end tests
Frontend tests
Backend API tests
Tool safety tests
Plugin tests
Memory tests
Packaging smoke tests
```

---

## 3. Backend Tests

Framework sugerido:

```txt
pytest
pytest-asyncio
httpx
```

Áreas obrigatórias:

* Providers.
* Agent Runtime.
* Core Orchestrator.
* Tools.
* Permissions.
* Memory.
* MCP.
* Plugins.
* Storage.
* Logs.
* API routes.

---

## 4. Frontend Tests

Framework sugerido:

```txt
Vitest
React Testing Library
Playwright
```

Testar:

* Renderização de telas.
* Formulários de agentes.
* Formulários de times.
* Providers.
* Workspaces.
* Timeline.
* Aprovações.
* Memory UI.
* MCP UI.
* Skills/plugins UI.

---

## 5. E2E Tests

Framework sugerido:

```txt
Playwright
```

Fluxos mínimos:

### Criar agente e executar

1. Abrir app.
2. Configurar provider mock.
3. Criar agente.
4. Executar agente.
5. Ver resposta.
6. Ver execução no histórico.

### Aprovação manual

1. Criar agente com terminal.
2. Rodar tarefa que chama `terminal.exec`.
3. Ver approval request.
4. Aprovar.
5. Ver resultado.
6. Ver audit log.

### Auto aprovação

1. Rodar execução em auto approval.
2. Tool crítica executa sem prompt.
3. Audit log é gerado.

### Memória

1. Criar memória.
2. Executar agente.
3. Ver memória usada na timeline.

---

## 6. Tool Safety Tests

Testes obrigatórios:

* Não ler fora do workspace.
* Não escrever fora do workspace.
* Não deletar fora do workspace.
* Não executar terminal sem capability.
* `blocked_tools` vence capability.
* Path traversal bloqueado.
* Timeout de terminal funciona.
* Logs mascaram segredos.

---

## 7. Provider Tests

### Ollama

Usar dois modos:

```txt
mock
real optional
```

Mock obrigatório em CI.

Real opcional localmente.

Testes:

* Health check.
* List models.
* Chat.
* Streaming.
* Embeddings.
* Modelo inexistente.
* Provider indisponível.

### OpenRouter

No CI, usar mock.

Testes:

* API key ausente.
* API key mascarada.
* Chat mock.
* Rate limit mock.
* Erro de provider.

---

## 8. Memory Tests

Testar:

* Criar memória global.
* Criar memória de agente.
* Criar memória de time.
* Buscar por texto.
* Buscar por embedding mock.
* Buscar respeitando escopo.
* Deduplicação.
* Links entre memórias.
* Registro de uso.

---

## 9. Plugin Tests

Testar:

* Importar plugin válido.
* Rejeitar manifesto inválido.
* Rejeitar namespace reservado.
* Registrar tool.
* Executar plugin tool.
* Timeout.
* Erro em plugin.
* Logs de plugin.
* Permissões de plugin.

---

## 10. MCP Tests

No MVP:

* MCP stdio mock.
* Registrar servidor.
* Testar conexão.
* Listar tools.
* Executar tool mock.
* Erro de conexão.
* Timeout.
* Audit log.

---

## 11. Logs/Audit Tests

Testar:

* Execução cria log.
* Tool cria audit log.
* Aprovação cria audit log.
* Auto aprovação cria audit log.
* Terminal registra comando.
* Segredos são mascarados.
* Export JSON funciona.

---

## 12. Packaging Smoke Tests

Após build Windows:

* App abre.
* Backend sobe.
* Health check responde.
* AppData é criado.
* SQLite é criado.
* Tela inicial carrega.
* App fecha sem deixar backend preso.

---

## 13. Fixtures

Criar fixtures para:

```txt
Temporary AppData
Temporary workspace
Mock provider
Mock embeddings
Mock MCP server
Mock plugin
Sample agents
Sample teams
Sample memories
```

Nunca testar em pastas reais do usuário.

---

## 14. CI

Para open-source, usar GitHub Actions futuramente.

Pipeline mínimo:

```txt
Backend tests
Frontend tests
Lint
Typecheck
Build frontend
```

Packaging completo pode ser manual inicialmente.

---

## 15. Critérios de Aceite

A estratégia de testes estará cumprida quando:

* Backend tiver testes dos módulos centrais.
* Frontend tiver testes básicos.
* E2E cobrir criar/executar agente.
* Tool safety tests impedirem acesso fora do workspace.
* Providers tiverem mocks.
* Memory tiver testes.
* Plugin SDK tiver testes.
* Logs/audit tiver testes.
* Build Windows tiver smoke test.
