# Tools do Claude Code → como implementar no AgentDesk

Guia de referência para portar o modelo de ferramentas do **Claude Code** para o
sistema de tools do AgentDesk. O AgentDesk já tem a infraestrutura (registry,
`BaseTool`, `input_schema`, permissões, approval, risco); este doc mostra **como
cada tool do Claude Code funciona** e **como mapeá-la** para uma tool nativa aqui.

---

## 1. Como as tools funcionam no Claude Code

O Claude Code expõe um conjunto pequeno e ortogonal de ferramentas. Os princípios
de design que valem a pena copiar:

1. **Cada tool faz uma coisa.** Ler, escrever, editar, buscar arquivo, buscar
   conteúdo e rodar shell são tools separadas — não uma "filesystem" gigante.
2. **Schema de entrada explícito.** Toda tool declara seus parâmetros, quais são
   obrigatórios e os defaults.
3. **Editar > reescrever.** A tool `Edit` faz **substituição exata de string**
   num arquivo já existente, em vez de reescrever o arquivo inteiro. Isso evita
   reenviar arquivos grandes (e o truncamento por `max_tokens`).
4. **Read-before-Edit.** O `Edit` exige que o arquivo tenha sido lido antes na
   conversa; e o `old_string` precisa casar exatamente (ou falha). Isso impede
   edição às cegas.
5. **Erros claros e acionáveis.** Quando algo falha, a mensagem diz exatamente o
   que corrigir (string não encontrada, não-único, path inexistente).
6. **Output enxuto.** Resultados grandes são truncados/paginados; nunca despejam
   o repositório inteiro no contexto.

---

## 2. Catálogo: Claude Code → AgentDesk

| Claude Code | O que faz | Equivalente no AgentDesk | Status |
|-------------|-----------|--------------------------|--------|
| **Read** | Lê arquivo (com offset/limit de linhas) | `filesystem.read` (`max_bytes` + `offset`/`limit`) | ✅ existe |
| **Write** | Cria/sobrescreve arquivo inteiro | `filesystem.write` (modos overwrite/append/create_only) | ✅ existe |
| **Edit** | **Substitui string exata** num arquivo | `filesystem.edit` | ✅ existe |
| **Glob** | Acha arquivos por padrão (`**/*.ts`) | `filesystem.search` (glob por nome) | ✅ parcial |
| **Grep** | Busca **conteúdo** por regex | `filesystem.grep` | ✅ existe |
| **Bash** | Roda comando shell | `terminal.exec` | ✅ existe |
| **WebFetch** | Baixa URL | `http.request` | ✅ existe |
| **Agent / Task** | Dispara subagente | `agent.call` / `team.execute` | ✅ existe |

O tripé **localizar → ler → editar** já está completo: `filesystem.grep` (buscar
conteúdo), `filesystem.read` com `offset`/`limit` (ler só o trecho) e
`filesystem.edit` (trocar a string exata) — tudo sem reescrever arquivos
inteiros. As próximas lacunas úteis estão em §7.

---

## 3. Anatomia de uma tool no AgentDesk

Toda tool herda de [`BaseTool`](../backend/app/tools/base.py) e implementa
`async def execute(arguments, context)`:

```python
class BaseTool(ABC):
    name: str = ""              # ex.: "filesystem.edit"  (sempre pontuado)
    description: str = ""        # vai no prompt do modelo
    capability: str = ""         # grupo de permissão (ver capabilities.py)
    critical: bool = False       # True => passa pelo fluxo de approval
    source: str = "core"         # core | plugin | mcp
    input_schema: Dict = {}      # parâmetros declarados
    output_schema: Dict = {}

    @abstractmethod
    async def execute(self, arguments, context: ToolExecutionContext) -> Dict:
        ...
```

O `context` ([`ToolExecutionContext`](../backend/app/tools/base.py)) dá acesso a
`execution_id`, `agent_id`, `db`, `approval_mode` e — o mais importante para
filesystem — `get_workspace_paths()` / `get_workspace_roots()`, que limitam a tool
às pastas autorizadas. **Sempre** passe o path por
[`assert_path_in_workspaces`](../backend/app/permissions/path_guard.py) antes de
tocar no disco.

### Passos para adicionar uma tool

1. Criar a classe em `backend/app/tools/core/<arquivo>.py`.
2. Registrá-la em `register_core_tools()` em
   [`registry.py`](../backend/app/tools/registry.py).
3. Em [`capabilities.py`](../backend/app/tools/capabilities.py):
   - adicionar o nome na `CAPABILITIES[<grupo>]`;
   - se mexe no disco/rede, adicionar em `CRITICAL_TOOLS` + `TOOL_RISK_LEVELS`;
   - adicionar uma linha em `TOOL_SUMMARIES` (texto do card de approval).
4. Escrever testes (espelhar `backend/tests/test_phase8_tools.py`).

O prompt que o modelo vê é montado automaticamente a partir de `name` +
`description` + `input_schema` pelo
[`PromptBuilder`](../backend/app/runtime/prompt_builder.py) — não precisa
documentar a tool em outro lugar.

---

## 4. Exemplo: `filesystem.edit` (substituição exata) — JÁ IMPLEMENTADO

> ✅ Esta tool já existe em
> [`backend/app/tools/core/filesystem_edit.py`](../backend/app/tools/core/filesystem_edit.py)
> e está registrada/coberta por testes
> ([`test_filesystem_edit.py`](../backend/tests/test_filesystem_edit.py)). O código
> abaixo é o modelo de referência.

Esta é a tool mais valiosa do conjunto. Em vez de reescrever `main.js` inteiro
(estourando `max_tokens` e truncando — ver [troubleshooting](./troubleshooting.md)),
o agente troca só o trecho que mudou.

```python
# backend/app/tools/core/filesystem_edit.py
from pathlib import Path
from typing import Any, Dict

from app.permissions.path_guard import assert_path_in_workspaces
from app.tools.base import BaseTool, ToolExecutionContext
from app.tools.errors import ToolError


class FilesystemEditTool(BaseTool):
    name = "filesystem.edit"
    description = (
        "Replaces an exact string in an existing file inside an authorized "
        "workspace. Prefer this over filesystem.write for small changes: it does "
        "NOT require resending the whole file. 'old_string' must match exactly "
        "and be unique (unless replace_all is true)."
    )
    capability = "filesystem_write"
    critical = True
    source = "core"
    input_schema = {
        "path": {"type": "string", "description": "File to edit.", "required": True},
        "old_string": {"type": "string", "description": "Exact text to replace.", "required": True},
        "new_string": {"type": "string", "description": "Replacement text.", "required": True},
        "replace_all": {"type": "boolean", "description": "Replace every occurrence.", "default": False},
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        path = arguments.get("path", "")
        old = arguments.get("old_string", "")
        new = arguments.get("new_string", "")
        replace_all = bool(arguments.get("replace_all", False))

        if not path:
            raise ToolError("MISSING_PATH", "Argument 'path' is required")
        if old == new:
            raise ToolError("NO_CHANGE", "old_string and new_string are identical")

        # Só pastas com permissão de escrita.
        write_paths = context.get_workspace_paths_with_permission("write")
        target = assert_path_in_workspaces(path, write_paths)
        if not target.exists() or target.is_dir():
            raise ToolError("PATH_NOT_FOUND", f"File '{path}' does not exist")

        text = target.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            raise ToolError("STRING_NOT_FOUND", "old_string not found in file")
        if count > 1 and not replace_all:
            raise ToolError(
                "STRING_NOT_UNIQUE",
                f"old_string appears {count} times; make it unique or set replace_all=true",
            )

        updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
        target.write_text(updated, encoding="utf-8")
        return {"path": str(target), "replacements": count if replace_all else 1}
```

Depois: registrar em `register_core_tools()`, e em `capabilities.py` adicionar
`"filesystem.edit"` em `CAPABILITIES["filesystem_write"]`, `CRITICAL_TOOLS`,
`TOOL_RISK_LEVELS` (`"medium"`) e `TOOL_SUMMARIES`.

---

## 5. `filesystem.grep` (busca por conteúdo) — JÁ IMPLEMENTADO

> ✅ Existe em
> [`backend/app/tools/core/filesystem_grep.py`](../backend/app/tools/core/filesystem_grep.py),
> registrada e com testes
> ([`test_filesystem_grep.py`](../backend/tests/test_filesystem_grep.py)).

`filesystem.search` acha **nomes** de arquivo; o `filesystem.grep` acha
**conteúdo** por regex, recursivamente, e devolve `{path, line, text}` com número
da linha. Parâmetros: `path`, `pattern`, `glob` (filtro de arquivo, ex.: `*.js`),
`case_insensitive`, `max_results`. É read-only (`capability=filesystem_read`,
`critical=False`), pula binários/arquivos grandes e trunca em `max_results`.

> Para grandes volumes, dá para evoluir usando `ripgrep` (`rg`) via subprocess
> quando disponível — é o que o Claude Code usa por baixo do Grep.

---

## 7. Próximas lacunas úteis

1. **`filesystem.multi_edit`** — aplicar N substituições atômicas no mesmo
   arquivo numa só chamada (tudo-ou-nada).
2. **`terminal.exec` em background/streaming** — rodar dev server / testes longos
   sem travar o turno.
3. **`web.search`** — buscar na web (hoje só `http.request`, que exige a URL).

> `filesystem.read` por linhas (`offset`/`limit`) já foi implementado — fecha o
> tripé localizar → ler → editar.

---

## 6. Boas práticas herdadas do Claude Code

- **Edit antes de Write.** Oriente o agente (no `system_prompt` / regras) a usar
  `filesystem.edit` para mudanças pontuais e só usar `filesystem.write` para
  arquivos novos. Isso reduz drasticamente truncamento por `max_tokens`.
- **Read antes de Edit.** Recomende ler o arquivo antes de editar; o `old_string`
  precisa bater exatamente.
- **Paths absolutos** dentro do workspace; nunca relativos ambíguos.
- **Erros que ensinam.** Códigos como `STRING_NOT_UNIQUE` dizem ao modelo
  exatamente como se corrigir na próxima tentativa.
- **Limite o output** (`max_bytes`, `max_results`) para não inundar o contexto.

---

## Referências no código

- Base/contexto: [`backend/app/tools/base.py`](../backend/app/tools/base.py)
- Registro: [`backend/app/tools/registry.py`](../backend/app/tools/registry.py)
- Permissões/risco: [`backend/app/tools/capabilities.py`](../backend/app/tools/capabilities.py)
- Guarda de path: [`backend/app/permissions/path_guard.py`](../backend/app/permissions/path_guard.py)
- Exemplos de tools: [`backend/app/tools/core/filesystem.py`](../backend/app/tools/core/filesystem.py), [`filesystem_write.py`](../backend/app/tools/core/filesystem_write.py)
- Protocolo de chamada (JSON): [`backend/app/runtime/parser.py`](../backend/app/runtime/parser.py)
