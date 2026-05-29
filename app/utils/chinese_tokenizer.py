import jieba


def tokenize(text: str) -> str:
    """Tokenize Chinese text using jieba, return space-separated tokens."""
    words = jieba.lcut(text)
    return " ".join(words)


def tokenize_for_tsquery(text: str) -> str:
    """Tokenize text and format as PostgreSQL tsquery OR expression.

    E.g. "你好世界" -> "你好 | 世界"
    """
    words = jieba.lcut(text)
    # Filter out whitespace and single-char punctuation
    tokens = [w.strip() for w in words if w.strip() and len(w.strip()) > 0]
    if not tokens:
        return ""
    return " | ".join(tokens)
