import uuid
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import ChunkBgeM3


async def vector_search(
    session: AsyncSession,
    kb_id: str,
    query_embedding: list[float],
    top_k: int = 5,
    similarity_threshold: float = 0.5,
) -> list[dict]:
    """Cosine distance search using pgvector.

    Returns list of dicts with keys: id, content, metadata, score (distance).
    """
    stmt = text("""
        SELECT id, content, metadata, embedding <=> :query_vec AS distance
        FROM chunk_bge_m3
        WHERE kb_id = :kb_id
        ORDER BY embedding <=> :query_vec
        LIMIT :top_k
    """)
    result = await session.execute(
        stmt,
        {
            "query_vec": str(query_embedding),
            "kb_id": uuid.UUID(kb_id),
            "top_k": top_k,
        },
    )
    rows = result.fetchall()
    results = []
    for row in rows:
        distance = float(row.distance) if row.distance is not None else 2.0
        if distance <= similarity_threshold * 2:  # threshold is cosine distance
            metadata = row.metadata
            title = metadata.get("title") if isinstance(metadata, dict) else None
            results.append({
                "id": str(row.id),
                "content": row.content,
                "title": title,
                "doc_id": None,
                "score": distance,
            })
    return results
