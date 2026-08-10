"""Small structured-output adapter for the Gemini Developer API."""

from __future__ import annotations

from typing import Protocol, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from .models import ProbeReport

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class GeneratingClient(Protocol):
    model: str
    usage: list[dict[str, int]]

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT: ...


class GeminiStructuredClient:
    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = genai.Client(api_key=api_key)
        self.usage: list[dict[str, int]] = []

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        return self._generate(system=system, contents=prompt, schema=schema)

    def generate_with_image(
        self,
        *,
        system: str,
        prompt: str,
        image: bytes,
        content_type: str,
        schema: type[SchemaT],
    ) -> SchemaT:
        return self.generate_with_images(
            system=system,
            prompt=prompt,
            images=[(image, content_type)],
            schema=schema,
        )

    def generate_with_images(
        self,
        *,
        system: str,
        prompt: str,
        images: list[tuple[bytes, str]],
        schema: type[SchemaT],
    ) -> SchemaT:
        return self.generate_with_media(system=system, prompt=prompt, media=images, schema=schema)

    def generate_with_media(
        self,
        *,
        system: str,
        prompt: str,
        media: list[tuple[bytes, str]],
        schema: type[SchemaT],
    ) -> SchemaT:
        if not media:
            raise ValueError("at least one media item is required")
        return self._generate(
            system=system,
            contents=[
                prompt,
                *[
                    types.Part.from_bytes(data=data, mime_type=content_type)
                    for data, content_type in media
                ],
            ],
            schema=schema,
        )

    def _generate(self, *, system: str, contents, schema: type[SchemaT]) -> SchemaT:
        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
        usage = response.usage_metadata
        self.usage.append(
            {
                "prompt_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
                "output_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
                "thinking_tokens": int(getattr(usage, "thoughts_token_count", 0) or 0),
                "total_tokens": int(getattr(usage, "total_token_count", 0) or 0),
            }
        )
        if isinstance(response.parsed, schema):
            return response.parsed
        if response.parsed is not None:
            return schema.model_validate(response.parsed)
        if not response.text:
            raise RuntimeError("Gemini returned no structured response")
        return schema.model_validate_json(response.text)


class ByFeelModelRouter:
    """Routes critical adversarial reasoning to main and routine work to Lite."""

    def __init__(self, *, main: GeneratingClient, lite: GeneratingClient) -> None:
        self.main = main
        self.lite = lite
        self.model = f"main={main.model},lite={lite.model}"

    @property
    def usage(self) -> list[dict[str, int]]:
        return [*self.main.usage, *self.lite.usage]

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        client = self.main if schema is ProbeReport else self.lite
        return client.generate(system=system, prompt=prompt, schema=schema)
