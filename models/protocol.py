"""Provider-neutral language-model request and response contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

class ModelError(RuntimeError):
    pass

@dataclass(frozen=True, kw_only=True)
class ModelRequest:
    prompt: str
    system: str
    max_tokens: int

@dataclass(frozen=True, kw_only=True)
class ModelResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model_id: str

class ModelAdapter(Protocol):
    def complete(
        self,
        request: ModelRequest,
        input_text: str | None = None,
        token: str | None = None,
    ) -> ModelResponse: ...
