# 09-computer-use-vision-pipeline.md

# AgentDesk — Fase A: Pipeline de Visão (imagens até o modelo)

> Parte de [08-computer-use-overview.md](08-computer-use-overview.md). Pré-requisito das fases B e C.

## 1. Objetivo

Permitir que imagens (screenshots em base64) cheguem ao modelo nos providers que suportam visão. Hoje o pipeline é 100% texto: `ChatMessage.content` é `str` e os providers Ollama/OpenRouter só serializam texto.

Esta fase é **autônoma e testável sozinha** — pode ser validada enviando uma imagem qualquer a um modelo multimodal e conferindo que ele a descreve, sem nenhum tool de computer-use ainda existir.

## 2. Escopo

- Estender o schema de mensagem para carregar imagens.
- Estender o provider **Ollama** para enviar `images` no `/api/chat`.
- Estender o provider **OpenRouter** para enviar blocos de imagem no formato content-parts.
- Detecção de capacidade multimodal (o que fazer quando o modelo não suporta imagem).
- Não inclui captura de tela, tools, nem loop (isso é fase B/C).

## 3. Mudanças de schema

`backend/app/providers/schemas.py`:

```python
class ImagePart(BaseModel):
    # Imagem inline em base64 (sem prefixo data-uri); o provider monta o formato final.
    base64: str
    media_type: str = "image/png"

class ChatMessage(BaseModel):
    role: str
    content: str
    images: List[ImagePart] = Field(default_factory=list)  # NOVO — vazio = comportamento atual
```

`ModelInfo` ganha flag de capacidade:

```python
class ModelInfo(BaseModel):
    id: str
    name: str
    context_window: int = 8192
    supports_vision: bool = False  # NOVO
```

Compatibilidade: `images` default vazio ⇒ todo caminho de texto existente continua idêntico.

## 4. Provider Ollama

`/api/chat` aceita `images: [base64...]` **por mensagem**. No builder de payload (`chat` e `stream_chat`):

```python
def _msg_to_ollama(m: ChatMessage) -> dict:
    out = {"role": m.role, "content": m.content}
    if m.images:
        out["images"] = [img.base64 for img in m.images]  # base64 puro, sem data-uri
    return out
```

Substituir os dois list-comprehensions atuais (`chat` e `stream_chat`) por essa função.

**Detecção de visão (Ollama):** `/api/show` retorna metadados/famílias do modelo. A detecção fina é frágil entre versões; estratégia robusta:
- Tentar enviar a imagem; se o modelo não for multimodal o Ollama ignora/erra.
- Manter uma allowlist de famílias conhecidas (`llava`, `gemma3`, `qwen2.5vl`, `llama3.2-vision`, `minicpm-v`, `moondream`) para popular `supports_vision` em `list_models`. A allowlist é um dict simples e documentado, fácil de estender.

## 5. Provider OpenRouter

Formato OpenAI content-parts (multimodal):

```python
def _msg_to_openrouter(m: ChatMessage) -> dict:
    if not m.images:
        return {"role": m.role, "content": m.content}
    parts = [{"type": "text", "text": m.content}]
    for img in m.images:
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{img.media_type};base64,{img.base64}"},
        })
    return {"role": m.role, "content": parts}
```

`supports_vision` em OpenRouter pode vir do campo `architecture.modality`/`input_modalities` da API de modelos do OpenRouter quando disponível; senão `False`.

## 6. Tratamento de erro

- Mensagem com imagem enviada a modelo **sem** visão: o runtime (fase C) decide a degradação; nesta fase o provider só repassa. Documentar que o provider **não** silencia imagens — quem decide é a camada acima, com base em `supports_vision`.
- Imagem grande demais: limite de lado maior (ex.: 1568px, downscale antes de codificar) será aplicado na **fase B** (camada de captura). Nesta fase o provider aceita o base64 como vier.

## 7. Critérios de aceite

1. `ChatMessage(images=[...])` serializa corretamente para Ollama (`images: [...]`) e OpenRouter (content-parts).
2. Caminho de texto puro (`images=[]`) produz payload **byte-idêntico** ao atual (sem regressão).
3. Teste de integração (marcado, opcional em CI): enviar PNG de teste a um modelo multimodal local e validar resposta não-vazia coerente.
4. `list_models` popula `supports_vision` corretamente para ao menos uma família local conhecida.

## 8. Testes

- Unit: `_msg_to_ollama` / `_msg_to_openrouter` com e sem imagens (snapshot do dict).
- Unit: backward-compat — request sem imagens gera payload idêntico ao baseline.
- Integração (opt-in via env/marker): round-trip real contra Ollama com modelo de visão.
