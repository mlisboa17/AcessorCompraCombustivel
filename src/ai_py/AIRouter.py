from __future__ import annotations

import os
import time
from typing import Optional

from .providers import ProviderCerebras, ProviderGroq, ProviderOpenRouter
from .types import AIContext, AIProvider, AIProviderError, AI_FRIENDLY_ERROR


class AIRouter:
    _providers: dict[str, AIProvider] = {
        "Groq": ProviderGroq(),
        "Cerebras": ProviderCerebras(),
        "OpenRouter": ProviderOpenRouter(),
    }
    _backoff_ms = [300, 600, 1000]

    @classmethod
    def handle(cls, input_text: str, context: Optional[AIContext] = None) -> str:
        last_error: Optional[Exception] = None
        provider_order = cls._provider_order()

        for index, provider in enumerate(provider_order):
            print(f"[AI Service] Iniciando requisição com provedor: {provider.name}")
            try:
                return cls._run_with_retries(provider, input_text, context)
            except Exception as exc:
                last_error = exc
                next_provider = provider_order[index + 1] if index + 1 < len(provider_order) else None
                if next_provider:
                    print(
                        f"[AI Critical] {provider.name} esgotou tentativas. "
                        f"Chaveando dinamicamente para Fallback {index + 1}: {next_provider.name}"
                    )

        print(f"[AI Critical] Todos os provedores falharam. Ultimo erro: {last_error}")
        return AI_FRIENDLY_ERROR

    @classmethod
    def _run_with_retries(cls, provider: AIProvider, input_text: str, context: Optional[AIContext]) -> str:
        max_attempts = min(max(cls._int_env("AI_PROVIDER_MAX_ATTEMPTS", 3), 2), 3)
        for attempt in range(1, max_attempts + 1):
            try:
                return provider.generate_response(input_text, context)
            except AIProviderError as exc:
                is_last = attempt == max_attempts
                if not exc.retryable or is_last:
                    raise
                status_text = f"código {exc.status_code}" if exc.status_code else str(exc)
                print(f"[AI Warning] {provider.name} falhou com {status_text}. Tentando novamente (Retry #{attempt})...")
                time.sleep(cls._backoff_ms[min(attempt - 1, len(cls._backoff_ms) - 1)] / 1000)

        raise AIProviderError(f"{provider.name} esgotou tentativas.", provider.name, retryable=True)

    @classmethod
    def _provider_order(cls) -> list[AIProvider]:
        default_order = ["Groq", "Cerebras", "OpenRouter"]
        env_order = [
            os.getenv("AI_PROVIDER_PRIMARY"),
            os.getenv("AI_PROVIDER_FALLBACK_1"),
            os.getenv("AI_PROVIDER_FALLBACK_2"),
        ]
        names = []
        for index, name in enumerate(env_order):
            normalized = cls._normalize_provider_name(name) or default_order[index]
            if normalized not in names:
                names.append(normalized)
        return [cls._providers[name] for name in names if name in cls._providers]

    @staticmethod
    def _normalize_provider_name(name: Optional[str]) -> Optional[str]:
        value = (name or "").strip().lower()
        if value == "groq":
            return "Groq"
        if value == "cerebras":
            return "Cerebras"
        if value in ("openrouter", "open-router"):
            return "OpenRouter"
        return None

    @staticmethod
    def _int_env(key: str, fallback: int) -> int:
        try:
            value = int(os.getenv(key, ""))
            return value if value > 0 else fallback
        except Exception:
            return fallback
