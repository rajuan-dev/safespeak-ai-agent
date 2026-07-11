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
        temperature: float = 0.2,
        model: str | None = None,
    ) -> dict[str, Any]:
        if not self.client:
            return fallback
        response = await self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            return json.loads(match.group(0)) if match else fallback

    async def text_completion(
        self, *, system: str, user: str, temperature: float = 0.2, model: str | None = None
    ) -> str:
        if not self.client:
            return ""
        response = await self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()

    async def vision_text_completion(
        self, *, instruction: str, image_data: str, model: str | None = None
    ) -> str:
        if not self.client:
            return ""
        response = await self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": {"url": image_data}},
                    ],
                }
            ],
        )
        return (response.choices[0].message.content or "").strip()


llm_service = LlmService()
