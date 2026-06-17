# 13-plugin-sdk.md

# AgentDesk — Plugin SDK Spec

## 1. Objetivo

Definir o SDK de plugins do AgentDesk.

O objetivo é permitir que desenvolvedores criem plugins locais capazes de adicionar:

* Tools.
* Skills.
* Templates.
* Workflows.
* Integrações.
* Assets.
* Configurações.

No MVP, plugins serão instalados localmente por pasta.

Marketplace fica para uma versão futura.

---

## 2. Princípios

Plugins devem ser:

* Locais.
* Portáveis.
* Versionados.
* Declarativos.
* Auditáveis.
* Desativáveis.
* Compatíveis com o sistema de permissões.
* Compatíveis com o Tool Registry.
* Compatíveis com logs/auditoria.

---

## 3. Estrutura de Plugin

Estrutura sugerida:

```txt
my-plugin/
  plugin.json
  README.md

  skills/
    report-writer.skill.json

  tools/
    generate_report.py
    search_data.py

  assets/
    icon.png

  config/
    defaults.json

  examples/
    example-agent.json
```

Arquivo obrigatório:

```txt
plugin.json
```

---

## 4. Plugin Manifest

Exemplo:

```json
{
  "id": "plugin_files_report",
  "name": "Files Report Plugin",
  "version": "0.1.0",
  "description": "Adiciona ferramentas para gerar relatórios sobre arquivos.",
  "author": "local",
  "homepage": "",
  "license": "MIT",
  "agentdesk_version": ">=0.1.0",
  "enabled_by_default": false,
  "permissions": [
    "filesystem_read"
  ],
  "skills": [
    "skills/report-writer.skill.json"
  ],
  "tools": [
    {
      "name": "files_report.generate",
      "description": "Gera relatório sobre arquivos.",
      "entrypoint": "tools/generate_report.py",
      "runtime": "python",
      "capability": "files_report",
      "critical": false,
      "input_schema": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string"
          }
        },
        "required": ["path"]
      }
    }
  ]
}
```

---

## 5. Regras de Namespace

Plugins devem usar namespace próprio.

Exemplo correto:

```txt
files_report.generate
github.create_issue
notion.create_page
```

Exemplo proibido:

```txt
filesystem.read
terminal.exec
memory.search
```

Regras:

* Plugin não pode sobrescrever core tool.
* Plugin não pode usar namespace `mcp`.
* Plugin não pode registrar tool sem prefixo.
* Nome da tool deve ser único.

---

## 6. Skill de Plugin

Skill dentro de plugin usa o mesmo formato de skill comum.

```json
{
  "id": "skill_report_writer",
  "name": "Escritor de Relatórios",
  "version": "0.1.0",
  "description": "Ajuda a escrever relatórios claros.",
  "tags": ["report", "writing"],
  "prompt": "Ao gerar relatórios, organize em resumo, achados, riscos e próximos passos.",
  "examples": []
}
```

---

## 7. Tool de Plugin

No MVP, tools de plugin podem ser scripts Python executados pelo backend.

Entrada da tool via JSON stdin.

Saída da tool via JSON stdout.

### Entrada

```json
{
  "arguments": {},
  "context": {
    "execution_id": "exec_001",
    "agent_id": "agent_001",
    "workspace_ids": []
  }
}
```

### Saída de Sucesso

```json
{
  "status": "success",
  "result": {}
}
```

### Saída de Erro

```json
{
  "status": "error",
  "error": {
    "code": "PLUGIN_TOOL_FAILED",
    "message": "Falha ao gerar relatório."
  }
}
```

---

## 8. Execução de Plugin Tool

Fluxo:

1. Agente solicita tool.
2. Tool Registry identifica que é plugin tool.
3. Permissions valida se agente pode usar.
4. Approval mode é aplicado.
5. Plugin Runner executa entrypoint.
6. Resultado volta ao Agent Runtime.
7. Logs e auditoria são salvos.

---

## 9. Plugin Runner

Responsável por executar tools de plugins.

MVP:

```txt
Python subprocess
```

Regras:

* Timeout obrigatório.
* Diretório de trabalho controlado.
* Entrada via JSON.
* Saída via JSON.
* Capturar stderr.
* Registrar logs.
* Mascarar segredos.
* Não permitir sobrescrever arquivos internos do AgentDesk sem permissão explícita.

---

## 10. Segurança

Plugins são potencialmente perigosos.

O sistema deve:

* Exibir aviso ao instalar plugin.
* Mostrar permissões solicitadas.
* Permitir ativar/desativar.
* Registrar toda execução.
* Respeitar approval mode.
* Respeitar workspaces.
* Aplicar timeout.
* Bloquear namespaces reservados.

No MVP, não é necessário sandbox avançado, mas a arquitetura deve permitir sandbox futuro.

---

## 11. Permissões Declaradas

Plugins devem declarar permissões.

Exemplos:

```txt
filesystem_read
filesystem_write
filesystem_delete
terminal
http
memory
```

Se uma plugin tool tentar usar uma capability não declarada, deve falhar.

---

## 12. Instalação Local

Formas suportadas no MVP:

```txt
Importar por pasta
Criar plugin básico pela UI
```

Fluxo de importação:

1. Usuário escolhe pasta.
2. Sistema procura `plugin.json`.
3. Valida manifesto.
4. Mostra resumo.
5. Mostra permissões.
6. Usuário confirma instalação.
7. Sistema copia plugin para AppData.
8. Registra plugin no SQLite.
9. Registra tools e skills.

---

## 13. Atualização de Plugin

No MVP, atualização pode ser manual.

Fluxo:

```txt
Desativar plugin antigo
Importar nova versão
Migrar configurações se possível
```

---

## 14. Desinstalação

Ao remover plugin:

* Desativar plugin.
* Remover tools do registry.
* Remover skills instaladas pelo plugin.
* Manter logs antigos.
* Opcionalmente apagar arquivos.

---

## 15. API Inicial

```txt
GET /api/plugins
GET /api/plugins/{plugin_id}
POST /api/plugins/import
POST /api/plugins/{plugin_id}/enable
POST /api/plugins/{plugin_id}/disable
DELETE /api/plugins/{plugin_id}
GET /api/plugins/{plugin_id}/tools
GET /api/plugins/{plugin_id}/skills
```

---

## 16. Validação de Manifesto

O sistema deve validar:

* `id` obrigatório.
* `name` obrigatório.
* `version` obrigatório.
* Tool names únicos.
* Namespaces válidos.
* EntryPoints existentes.
* Skills existentes.
* Permissões declaradas.
* Versão compatível do AgentDesk.

---

## 17. Futuro Marketplace

Fora do MVP, mas a estrutura deve prever:

* Repositório remoto de plugins.
* Assinatura/verificação.
* Avaliações.
* Versões.
* Atualizações automáticas.
* Dependências.

---

## 18. Critérios de Aceite

O Plugin SDK estará pronto quando:

* Um plugin local puder ser importado por pasta.
* O manifesto for validado.
* Plugin puder registrar skills.
* Plugin puder registrar tools.
* Plugin tools aparecerem no Tool Registry.
* Agentes puderem usar plugin tools autorizadas.
* Execuções de plugin gerarem audit logs.
* Plugins puderem ser ativados/desativados.
* Plugin não puder sobrescrever core tools.
* Plugin respeitar workspaces e approval mode.
