"""Strict structured batch input/output contracts."""

from dataclasses import dataclass, field
import json
import re
from typing import Any

from common.config import OutputConfig


@dataclass(frozen=True)
class BatchItem:
    id: str
    title: str
    source: str
    published_at: str
    content: str


@dataclass(frozen=True)
class BatchEntryResult:
    id: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    why_it_matters: str | None = None
    topics: list[str] = field(default_factory=list)


@dataclass
class BatchParseResult:
    valid: dict[str, BatchEntryResult] = field(default_factory=dict)
    missing_ids: set[str] = field(default_factory=set)
    invalid_ids: set[str] = field(default_factory=set)
    unknown_ids: set[str] = field(default_factory=set)
    error: str | None = None


def build_entry_batch_payload(items: list[BatchItem]) -> str:
    return json.dumps(
        {
            "entries": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "source": item.source,
                    "published_at": item.published_at,
                    "content": item.content,
                }
                for item in items
            ]
        },
        ensure_ascii=False,
    )


def _decode(raw: str) -> Any:
    stripped = raw.strip()
    match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE
    )
    return json.loads(match.group(1) if match else stripped)


def parse_entry_batch_response(raw: str, expected_ids: set[str]) -> BatchParseResult:
    result = BatchParseResult(missing_ids=set(expected_ids))
    try:
        data = _decode(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        result.error = f"invalid JSON: {exc}"
        return result
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        result.error = "response must contain entries list"
        return result
    seen = set()
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("id"), (str, int)):
            continue
        item_id = str(item["id"])
        if item_id not in expected_ids:
            result.unknown_ids.add(item_id)
            continue
        if item_id in seen:
            result.invalid_ids.add(item_id)
            result.valid.pop(item_id, None)
            continue
        seen.add(item_id)
        result.missing_ids.discard(item_id)
        summary = item.get("summary")
        arrays_ok = all(
            isinstance(item.get(key, []), list)
            and all(isinstance(v, str) for v in item.get(key, []))
            for key in ("key_points", "topics")
        )
        why = item.get("why_it_matters")
        if (
            not isinstance(summary, str)
            or not summary.strip()
            or not arrays_ok
            or (why is not None and not isinstance(why, str))
        ):
            result.invalid_ids.add(item_id)
            continue
        result.valid[item_id] = BatchEntryResult(
            item_id,
            summary.strip(),
            item.get("key_points", []),
            why,
            item.get("topics", []),
        )
    result.missing_ids -= result.invalid_ids
    return result


def render_entry_summary(result: BatchEntryResult, output_config: OutputConfig) -> str:
    if not result.key_points and not result.why_it_matters:
        return result.summary
    parts = [f"#### {output_config.heading}", ""]
    for point in result.key_points[: output_config.max_bullets]:
        parts.append(f"- {point}")
    if result.key_points:
        parts.append("")
    if output_config.include_why_it_matters and result.why_it_matters:
        parts.append(f"**Why it matters:** {result.why_it_matters}")
    return "\n".join(parts).strip()
