"""Anthropic Claude adapter for LLMPort.

Structured outputs use forced tool-use: the schema becomes a tool's
input_schema, tool_choice pins it, and the tool input is validated with
Pydantic (one retry on validation failure). Every call is logged with
tokens/latency under its prompt_name — LLM spend is a first-class metric.
"""

import time
from collections.abc import AsyncIterator
from typing import cast

import structlog
from anthropic import AsyncAnthropic
from anthropic.types import ContentBlockParam, MessageParam, ToolParam
from pydantic import ValidationError

from forge.api.errors import UpstreamError
from forge.config import get_settings
from forge.services.ports import ChatMessage, T

logger = structlog.get_logger(__name__)


class AnthropicLLM:
    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._default_model = settings.llm_pipeline_model

    async def complete_structured(
        self,
        *,
        prompt_name: str,
        system: str,
        user: str,
        schema: type[T],
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> T:
        tool: ToolParam = {
            "name": "emit_result",
            "description": f"Emit the {schema.__name__} result.",
            "input_schema": schema.model_json_schema(),
        }
        messages: list[MessageParam] = [{"role": "user", "content": user}]
        last_error: Exception | None = None
        for attempt in range(2):
            started = time.monotonic()
            response = await self._client.messages.create(
                model=model or self._default_model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": "emit_result"},
            )
            self._log(prompt_name, response, started)
            tool_input = next(
                (block.input for block in response.content if block.type == "tool_use"), None
            )
            try:
                return schema.model_validate(tool_input)
            except ValidationError as exc:
                last_error = exc
                logger.warning("llm.invalid_structured_output", prompt=prompt_name, attempt=attempt)
                messages = [
                    *messages,
                    {
                        "role": "assistant",
                        "content": cast(list[ContentBlockParam], response.content),
                    },
                    {
                        "role": "user",
                        "content": f"The result failed validation: {exc}. Emit it again, fixed.",
                    },
                ]
        raise UpstreamError(f"LLM structured output failed validation for {prompt_name}") from (
            last_error
        )

    async def complete_text(
        self,
        *,
        prompt_name: str,
        system: str,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        started = time.monotonic()
        response = await self._client.messages.create(
            model=model or self._default_model,
            max_tokens=max_tokens,
            system=system,
            messages=[m.model_dump() for m in messages],  # type: ignore[misc]
        )
        self._log(prompt_name, response, started)
        return "".join(block.text for block in response.content if block.type == "text")

    async def stream_text(
        self,
        *,
        prompt_name: str,
        system: str,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        started = time.monotonic()
        async with self._client.messages.stream(
            model=model or self._default_model,
            max_tokens=max_tokens,
            system=system,
            messages=[m.model_dump() for m in messages],  # type: ignore[misc]
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
        self._log(prompt_name, final, started)

    def _log(self, prompt_name: str, response: object, started: float) -> None:
        usage = getattr(response, "usage", None)
        logger.info(
            "llm.call",
            prompt=prompt_name,
            model=getattr(response, "model", "unknown"),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
