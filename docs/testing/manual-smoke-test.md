# AgentDesk Manual Smoke Test

## Ambiente

- Windows:
- Python:
- Node:
- Commit:
- Build:

## Checklist

### Startup
- [ ] Portable abre
- [ ] Backend inicia
- [ ] Dashboard carrega
- [ ] Logs sao criados

### Provider
- [ ] Criar provider Ollama
- [ ] Testar health com Ollama desligado mostra erro amigavel
- [ ] Testar health com Ollama ligado funciona

### Agent
- [ ] Criar agente
- [ ] Executar agente simples
- [ ] Timeline aparece
- [ ] Resultado final aparece

### Tools
- [ ] Criar workspace temporario
- [ ] filesystem.list funciona
- [ ] filesystem.read funciona
- [ ] filesystem.write pede approval manual
- [ ] terminal.exec pede approval manual

### Memory
- [ ] Criar memoria
- [ ] Buscar memoria
- [ ] Execucao injeta memoria

### Teams
- [ ] Criar time
- [ ] Executar time
- [ ] Timeline multiagente aparece

### Skills
- [ ] Criar skill
- [ ] Associar skill a agente
- [ ] Execucao carrega skill

### Plugins
- [ ] Importar sample plugin
- [ ] Ativar plugin
- [ ] Executar plugin tool

### MCP
- [ ] Cadastrar MCP mock
- [ ] Testar conexao
- [ ] Ver tools MCP

### Audit/Export
- [ ] Audit Logs registra acoes
- [ ] Export JSON funciona
- [ ] Export Markdown funciona

### Shutdown
- [ ] Fechar app
- [ ] Backend encerra
