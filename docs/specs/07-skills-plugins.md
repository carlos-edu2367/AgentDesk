# 07-skills-plugins.md

# AgentDesk — Skills & Plugins Spec

## 1. Objetivo

Definir como o AgentDesk cria, instala, organiza e executa skills e plugins locais.

Skills são comportamentos leves baseados em prompt/template.

Plugins são pacotes maiores que podem conter skills, tools, configurações e assets.

---

## 2. Diferença entre Skill e Plugin

### Skill

Uma skill contém:

* Nome.
* Descrição.
* Prompt.
* Template.
* Exemplos.
* Tags.

Não executa código diretamente.

### Plugin

Um plugin pode conter:

* Skills.
* Tools.
* Configurações.
* Manifesto.
* Assets.
* Dependências locais.

---

## 3. Estrutura Local

```txt
%APPDATA%/AgentDesk/
  skills/
    installed/
    custom/

  plugins/
    installed/
    custom/
```

---

## 4. Skill Manifest

```json
{
  "id": "skill_report_writer",
  "name": "Escritor de Relatórios",
  "version": "0.1.0",
  "description": "Ajuda agentes a escrever relatórios claros.",
  "tags": ["writing", "reports"],
  "prompt": "Ao gerar relatórios, organize em resumo, achados, riscos e próximos passos.",
  "examples": []
}
```

---

## 5. Plugin Manifest

```json
{
  "id": "plugin_files_report",
  "name": "Files Report Plugin",
  "version": "0.1.0",
  "description": "Plugin para relatórios de arquivos.",
  "author": "local",
  "skills": [
    "./skills/file_report.skill.json"
  ],
  "tools": [
    {
      "name": "files_report.generate",
      "description": "Gera relatório sobre arquivos.",
      "entrypoint": "tools/generate.py",
      "critical": false
    }
  ],
  "permissions": [
    "filesystem_read"
  ]
}
```

---

## 6. Instalação Local

No MVP, suportar:

* Criar skill pela interface.
* Importar skill `.json`.
* Criar plugin local.
* Importar plugin por pasta.
* Ativar/desativar plugin.
* Associar skill/plugin a agente.

Marketplace fica fora do MVP.

---

## 7. Skills no Runtime

Skills ativas devem ser injetadas no prompt do agente.

Formato no prompt:

```txt
[ACTIVE SKILL: Escritor de Relatórios]
Ao gerar relatórios, organize em resumo, achados, riscos e próximos passos.
```

---

## 8. Plugin Tools

Tools de plugin devem ser registradas no Tool Registry.

Regras:

* Namespace obrigatório.
* Não pode sobrescrever core tools.
* Deve passar por permissões.
* Deve gerar auditoria.
* Tools críticas pedem aprovação no modo manual.

---

## 9. Segurança

Plugins podem executar código, então devem ser tratados como potencialmente perigosos.

No MVP:

* Instalação local deve exibir aviso.
* Tools de plugin devem declarar permissões.
* Usuário deve ativar plugin manualmente.
* Auto aprovação permite execução sem confirmação.
* Logs devem registrar uso.

---

## 10. Interface

Tela Skills:

* Listar skills.
* Criar skill.
* Editar skill.
* Excluir skill.
* Importar/exportar skill.
* Associar a agente/time.

Tela Plugins:

* Listar plugins.
* Importar plugin local.
* Criar plugin básico.
* Ativar/desativar.
* Ver tools/skills incluídas.
* Ver permissões solicitadas.

---

## 11. API Inicial

```txt
GET /api/skills
POST /api/skills
PUT /api/skills/{skill_id}
DELETE /api/skills/{skill_id}

GET /api/plugins
POST /api/plugins/import
POST /api/plugins/{plugin_id}/enable
POST /api/plugins/{plugin_id}/disable
```

---

## 12. Critérios de Aceite

O módulo estará pronto quando:

* Usuário conseguir criar skills.
* Usuário conseguir associar skills a agentes.
* Skills forem injetadas no prompt.
* Usuário conseguir importar plugin local.
* Plugins registrarem tools.
* Plugin tools passarem por permissões.
* Uso de plugin aparecer nos logs.
