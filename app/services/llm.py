import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings


class LlmService:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.OPENAI_MODEL
        self.client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

    async def json_completion(
        self,
        *,
        system: str,
        user: str,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.client:
            return fallback
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            return json.loads(match.group(0)) if match else fallback


llm_service = LlmService()
