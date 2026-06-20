from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from .types import AIContext, AIProvider, AIProviderError, build_messages, is_retryable_status


def _env(key: str, provider: str) -> str:
    value = os.getenv(key)
    if not value:
        raise AIProviderError(f"Variavel de ambiente ausente: {key}", provider, retryable=False)
    return value


def _int_env(key: str, fallback: int) -> int:
    try:
        value = int(os.getenv(key, ""))
        return value if value > 0 else fallback
    except Exception:
        return fallback


def _post_json(provider: str, api_url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    timeout = _int_env("AI_PROVIDER_TIMEOUT_MS", 7000) / 1000
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AIProviderError(
            f"{provider} falhou com HTTP {exc.code}.",
            provider,
            retryable=is_retryable_status(exc.code),
            status_code=exc.code,
        ) from exc
    except TimeoutError as exc:
        raise AIProviderError(f"Timeout ao chamar {provider}.", provider, retryable=True) from exc
    except Exception as exc:
        raise AIProviderError(f"Falha de rede ao chamar {provider}.", provider, retryable=True) from exc


class ProviderGroq(AIProvider):
    name = "Groq"

    def generate_response(self, input_text: str, context: Optional[AIContext] = None) -> str:
        api_url = _env("GROQ_API_URL", self.name)
        api_key = _env("GROQ_API_KEY", self.name)
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        context = context or AIContext()

        data = _post_json(
            self.name,
            api_url,
            api_key,
            {
                "model": model,
                "messages": build_messages(input_text, context),
                "temperature": context.temperature,
                "max_tokens": context.max_tokens,
            },
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("Resposta invalida recebida do Groq.", self.name, retryable=False)
        return content.strip()


class ProviderCerebras(AIProvider):
    name = "Cerebras"

    def generate_response(self, input_text: str, context: Optional[AIContext] = None) -> str:
        api_url = _env("CEREBRAS_API_URL", self.name)
        api_key = _env("CEREBRAS_API_KEY", self.name)
        model = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
        context = context or AIContext()

        data = _post_json(
            self.name,
            api_url,
            api_key,
            {
                "model": model,
                "messages": build_messages(input_text, context),
                "temperature": context.temperature,
                "max_tokens": context.max_tokens,
            },
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("Resposta invalida recebida da Cerebras.", self.name, retryable=False)
        return content.strip()


class ProviderOpenRouter(AIProvider):
    name = "OpenRouter"

    def generate_response(self, input_text: str, context: Optional[AIContext] = None) -> str:
        api_url = _env("OPENROUTER_API_URL", self.name)
        api_key = _env("OPENROUTER_API_KEY", self.name)
        model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
        context = context or AIContext()

        data = _post_json(
            self.name,
            api_url,
            api_key,
            {
                "model": model,
                "messages": build_messages(input_text, context),
                "temperature": context.temperature,
                "max_tokens": context.max_tokens,
            },
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("Resposta invalida recebida do OpenRouter.", self.name, retryable=False)
        return content.strip()
