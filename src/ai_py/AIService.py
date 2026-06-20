from __future__ import annotations

from typing import Optional

from .AIRouter import AIRouter
from .types import AIContext


class AIService:
    def generate(self, input_text: str, context: Optional[AIContext] = None) -> str:
        return AIRouter.handle(input_text, context)


ai_service = AIService()
