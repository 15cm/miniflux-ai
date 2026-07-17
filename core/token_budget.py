"""Token-aware truncation and stable batch packing."""

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _encoding():
    try:
        import tiktoken

        return tiktoken.get_encoding("o200k_base")
    except ImportError:
        return None


def count_tokens(text: str) -> int:
    encoding = _encoding()
    if encoding is not None:
        return len(encoding.encode(text))
    # Conservative dependency-free fallback for bootstrapping environments.
    return len(text.encode("utf-8"))


def truncate_tokens(text: str, limit: int) -> tuple[str, bool]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    encoding = _encoding()
    if encoding is not None:
        tokens = encoding.encode(text)
        if len(tokens) <= limit:
            return text, False
        return encoding.decode(tokens[:limit]), True
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


def pack_items(
    items: list[dict[str, Any]],
    *,
    size: int,
    max_input_tokens: int,
    item_token_key: str = "token_count",
    overhead_tokens: int = 0,
) -> list[list[dict[str, Any]]]:
    if size < 1 or max_input_tokens < 1:
        raise ValueError("size and max_input_tokens must be positive")
    batches: list[list[dict[str, Any]]] = []
    batch: list[dict[str, Any]] = []
    used = overhead_tokens
    for item in items:
        tokens = item.get(item_token_key)
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise ValueError(f"item {item.get('id', '?')} has invalid {item_token_key}")
        if batch and (len(batch) >= size or used + tokens > max_input_tokens):
            batches.append(batch)
            batch, used = [], overhead_tokens
        batch.append(item)
        used += tokens
    if batch:
        batches.append(batch)
    return batches
