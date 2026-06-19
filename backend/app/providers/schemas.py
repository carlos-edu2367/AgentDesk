from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class ProviderHealth(BaseModel):
    status: bool
    details: Dict[str, Any] = Field(default_factory=dict)

class ModelInfo(BaseModel):
    id: str
    name: str
    context_window: int = 8192

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

class ChatRequest(BaseModel):
    provider_id: str
    model: str
    messages: List[ChatMessage]
    temperature: float = 0.4
    top_p: float = 0.9
    context_window: int = 8192
    max_tokens: int = 2048
    stream: bool = False
    tools: List[Dict[str, Any]] = Field(default_factory=list)

class ChatResponse(BaseModel):
    provider_id: str
    model: str
    content: str
    usage: ChatUsage = Field(default_factory=ChatUsage)
    raw: Dict[str, Any] = Field(default_factory=dict)

class ModelChunk(BaseModel):
    type: str = "model_chunk"
    provider_id: str
    model: str
    content_delta: str = ""
    done: bool = False
    usage: Optional[ChatUsage] = None

class EmbeddingRequest(BaseModel):
    model: str
    input: str

class EmbeddingResponse(BaseModel):
    model: str
    embedding: List[float]
