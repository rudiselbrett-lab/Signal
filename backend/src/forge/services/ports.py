"""Shared service-level ports for external AI providers.

Services depend on these Protocols; adapters implement them. Swapping
providers (or models) never touches service code.
"""

from collections.abc import AsyncIterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class LLMPort(Protocol):
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
        """One-shot structured completion validated against `schema`."""
        ...

    async def complete_text(
        self,
        *,
        prompt_name: str,
        system: str,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str: ...

    def stream_text(
        self,
        *,
        prompt_name: str,
        system: str,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]: ...


class EmbeddingPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
