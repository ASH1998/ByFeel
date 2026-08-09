"""Small structured-output adapter for the Gemini Developer API."""

from __future__ import annotations

from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class GeminiStructuredClient:
    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = genai.Client(api_key=api_key)

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            ),
        )
        if isinstance(response.parsed, schema):
            return response.parsed
        if response.parsed is not None:
            return schema.model_validate(response.parsed)
        if not response.text:
            raise RuntimeError("Gemini returned no structured response")
        return schema.model_validate_json(response.text)
