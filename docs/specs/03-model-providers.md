# 03-model-providers.md

# AgentDesk — Model Providers Spec

## 1. Objetivo

O módulo Model Providers é responsável por abstrair o acesso a modelos de IA usados pelos agentes.

No MVP, o AgentDesk deve suportar:

* Ollama para modelos locais.
* OpenRouter para modelos remotos via API key.

Cada agente pode definir seu próprio provider, modelo e parâmetros.

---

## 2. Responsabilidades

O módulo deve:

* Cadastrar providers.
* Validar conexão com provider.
* Listar modelos disponíveis quando possível.
* Executar chamadas de chat/completion.
* Suportar streaming.
* Suportar parâmetros por agente.
* Retornar erros padronizados.
* Expor health check.
* Permitir configuração de janela de contexto.
* Permitir uso de embeddings via Ollama.

---

## 3. Providers do MVP

### Ollama

Usado para:

* Chat local.
* Modelos locais.
* Embeddings locais.

Endpoint padrão:

```txt
http://localhost:11434
```

### OpenRouter

Usado para:

* Modelos remotos.
* Modelos pagos.
* Modelos com mais capacidade.

Endpoint padrão:

```txt
https://openrouter.ai/api/v1
```

---

## 4. Provider Config

Arquivo:

```txt
%APPDATA%/AgentDesk/config/providers.config.json
```

Exemplo:

```json
{
  "providers": [
    {
      "id": "ollama_local",
      "type": "ollama",
      "name": "Ollama Local",
      "base_url": "http://localhost:11434",
      "enabled": true
    },
    {
      "id": "openrouter_default",
      "type": "openrouter",
      "name": "OpenRouter",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "",
      "enabled": false
    }
  ],
  "embedding_provider": {
    "type": "ollama",
    "model": "nomic-embed-text",
    "base_url": "http://localhost:11434"
  }
}
```

---

## 5. Model Config por Agente

Cada agente deve poder configurar:

```json
{
  "provider_id": "ollama_local",
  "model": "qwen3:8b",
  "temperature": 0.4,
  "top_p": 0.9,
  "context_window": 8192,
  "max_tokens": 2048,
  "stream": true
}
```

Campos opcionais futuros:

```json
{
  "frequency_penalty": 0,
  "presence_penalty": 0,
  "seed": null,
  "stop": []
}
```

---

## 6. Interface Interna

Interface Python sugerida:

```python
class ModelProvider:
    async def health_check(self) -> ProviderHealth:
        ...

    async def list_models(self) -> list[ModelInfo]:
        ...

    async def chat(self, request: ChatRequest) -> ChatResponse:
        ...

    async def stream_chat(self, request: ChatRequest):
        ...

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        ...
```

---

## 7. ChatRequest

```json
{
  "provider_id": "ollama_local",
  "model": "qwen3:8b",
  "messages": [
    {
      "role": "system",
      "content": "Você é um agente útil."
    },
    {
      "role": "user",
      "content": "Organize meus arquivos."
    }
  ],
  "temperature": 0.4,
  "top_p": 0.9,
  "context_window": 8192,
  "max_tokens": 2048,
  "stream": true,
  "tools": []
}
```

---

## 8. ChatResponse

```json
{
  "provider_id": "ollama_local",
  "model": "qwen3:8b",
  "content": "Resposta do modelo",
  "usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 300,
    "total_tokens": 1300
  },
  "raw": {}
}
```

---

## 9. Streaming

O streaming deve emitir chunks padronizados.

```json
{
  "type": "model_chunk",
  "provider_id": "ollama_local",
  "model": "qwen3:8b",
  "content_delta": "texto parcial",
  "done": false
}
```

Evento final:

```json
{
  "type": "model_completed",
  "provider_id": "ollama_local",
  "model": "qwen3:8b",
  "done": true,
  "usage": {}
}
```

---

## 10. Ollama Provider

### Health Check

```txt
GET /api/tags
```

O sistema deve verificar:

* Ollama está rodando.
* Base URL responde.
* Modelo configurado existe.

### List Models

```txt
GET /api/tags
```

### Chat

Usar endpoint:

```txt
POST /api/chat
```

### Embeddings

Usar endpoint:

```txt
POST /api/embeddings
```

Modelo sugerido:

```txt
nomic-embed-text
```

---

## 11. OpenRouter Provider

### Health Check

Validar:

* API key preenchida.
* Requisição simples para endpoint de modelos.
* Provider habilitado.

### List Models

Usar endpoint compatível com OpenAI:

```txt
GET /models
```

### Chat

Usar:

```txt
POST /chat/completions
```

---

## 12. Segurança da API Key

No MVP, a API key pode ser salva localmente em arquivo de configuração.

Como o sistema é local, criptografia não é obrigatória no MVP.

Porém, o arquivo deve ficar em:

```txt
%APPDATA%/AgentDesk/config/providers.config.json
```

E nunca deve ser salvo em logs.

Regras:

* Não logar API key.
* Não enviar API key para agentes.
* Não exibir API key completa no frontend.
* Mostrar apenas mascarado: `sk-or-...abcd`.

---

## 13. Erros Padronizados

```json
{
  "code": "PROVIDER_UNAVAILABLE",
  "message": "O provider não está disponível.",
  "details": {}
}
```

Códigos iniciais:

```txt
PROVIDER_UNAVAILABLE
MODEL_NOT_FOUND
API_KEY_MISSING
API_KEY_INVALID
REQUEST_TIMEOUT
CONTEXT_TOO_LARGE
RATE_LIMITED
UNKNOWN_PROVIDER_ERROR
```

---

## 14. Context Window

O usuário deve poder configurar a janela de contexto por agente.

O runtime deve respeitar esse limite ao montar prompt.

Se o contexto exceder o limite:

1. Reduzir histórico.
2. Reduzir memórias.
3. Reduzir documentos.
4. Se ainda exceder, retornar erro controlado.

---

## 15. Testes

Testes mínimos:

* Health check Ollama.
* Health check OpenRouter.
* Listar modelos Ollama.
* Chat Ollama.
* Chat OpenRouter com mock.
* Streaming Ollama.
* Embedding Ollama.
* Erro de modelo inexistente.
* Erro de provider indisponível.
* API key não deve aparecer em logs.

---

## 16. Critérios de Aceite

O módulo estará pronto quando:

* O usuário conseguir cadastrar Ollama.
* O usuário conseguir cadastrar OpenRouter.
* O usuário conseguir selecionar provider/modelo por agente.
* O sistema conseguir validar se Ollama está rodando.
* O sistema conseguir listar modelos locais.
* O sistema conseguir chamar modelo local.
* O sistema conseguir chamar modelo OpenRouter.
* O sistema conseguir fazer streaming.
* O sistema conseguir gerar embeddings locais.
* Erros forem tratados de forma clara.
