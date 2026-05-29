from typing import Any


def rrf_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank_i))."""
    by_id: dict[str, dict] = {}
    vector_ranks: dict[str, int] = {}
    keyword_ranks: dict[str, int] = {}

    for i, r in enumerate(vector_results):
        rid = r["id"]
        by_id[rid] = r
        vector_ranks[rid] = i + 1

    for i, r in enumerate(keyword_results):
        rid = r["id"]
        by_id.setdefault(rid, r)
        keyword_ranks[rid] = i + 1

    results = []
    for rid, original in by_id.items():
        v_rank = vector_ranks.get(rid)
        k_rank = keyword_ranks.get(rid)
        score = 0.0
        if v_rank is not None:
            score += 1.0 / (k + v_rank)
        if k_rank is not None:
            score += 1.0 / (k + k_rank)
        results.append({
            "id": rid,
            "content": original["content"],
            "title": original.get("title"),
            "doc_id": original.get("doc_id"),
            "score": score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
