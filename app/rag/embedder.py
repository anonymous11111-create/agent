import httpx

from app.config import settings


async def embed_text(text: str) -> list[float]:
    """Call Ollama bge-m3 to get embedding vector."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={"model": settings.OLLAMA_EMBEDDING_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embedding"]
