"""OpenAI embeddings adapter (text-embedding-3-large @ 1536 dims)."""

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from forge.config import get_settings

BATCH_SIZE = 100


class OpenAIEmbedder:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            results.extend(await self._embed_batch(texts[start : start + BATCH_SIZE]))
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=20), reraise=True)
    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=batch,
            dimensions=self._dimensions,
        )
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
