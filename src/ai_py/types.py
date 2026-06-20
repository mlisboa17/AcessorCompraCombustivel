from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


AI_FRIENDLY_ERROR = "Serviço de IA temporariamente indisponível."


@dataclass
class AIContext:
    system_prompt: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    temperature: float = 0.2
    max_tokens: int = 700


class AIProviderError(Exception):
    def __init__(self, message: str, provider: str, retryable: bool = True, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code


class AIProvider:
    name: str

    def generate_response(self, input_text: str, context: Optional[AIContext] = None) -> str:
        raise NotImplementedError


def is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def build_messages(input_text: str, context: Optional[AIContext] = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if context and context.system_prompt:
        messages.append({"role": "system", "content": context.system_prompt})
    messages.append({"role": "user", "content": input_text})
    return messages
