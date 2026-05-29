import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.chinese_tokenizer import tokenize_for_tsquery


async def keyword_search(
    session: AsyncSession,
    kb_id: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.01,
) -> list[dict]:
    """PostgreSQL full-text search using ts_rank_cd.

    Uses jieba tokenization for Chinese text to build tsquery.
    """
    ts_query_str = tokenize_for_tsquery(query)
    if not ts_query_str:
        return []

    stmt = text("""
        SELECT id, content, metadata,
               ts_rank_cd(content_tsv, to_tsquery('simple', :ts_query)) AS rank
        FROM chunk_bge_m3
        WHERE kb_id = :kb_id
          AND content_tsv @@ to_tsquery('simple', :ts_query)
        ORDER BY rank DESC
        LIMIT :top_k
    """)
    result = await session.execute(
        stmt,
        {
            "ts_query": ts_query_str,
            "kb_id": uuid.UUID(kb_id),
            "top_k": top_k,
        },
    )
    rows = result.fetchall()
    results = []
    for row in rows:
        rank = float(row.rank) if row.rank is not None else 0.0
        if rank >= threshold:
            metadata = row.metadata
            title = metadata.get("title") if isinstance(metadata, dict) else None
            results.append({
                "id": str(row.id),
                "content": row.content,
                "title": title,
                "doc_id": None,
                "score": rank,
            })
    return results
