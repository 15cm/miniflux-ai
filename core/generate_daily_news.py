"""Legacy daily news plus bounded structured map/reduce mode."""

import concurrent.futures
import json
import time
from uuid import uuid4

from common import logger
from common.config import Config
from core.deduplicate import deduplicate_entries
from core.entry_filter import source_allowed
from core.get_ai_result import get_ai_json_result, get_ai_result
from core.render_daily_news import render_daily_news
from core.render_input import render_ai_news_input
from core.storage import DailyReport, SummaryStore
from core.token_budget import count_tokens, pack_items

config = Config()


def _refresh(miniflux_client):
    feeds = miniflux_client.get_feeds()
    feed_id = next(
        (item["id"] for item in feeds if "Newsᴬᴵ for you" in item["title"]), None
    )
    if feed_id:
        miniflux_client.refresh_feed(feed_id)


def _read_legacy_entries():
    try:
        with open("entries.json", encoding="utf8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _legacy_entry(row):
    return {
        "feed": {
            "site_url": row.get("site_url"),
            "category": {"title": row.get("category")},
        }
    }


def _filter_legacy_entries(rows):
    agent = config.agents.get(config.ai_news_batching.summary_agent)
    return [row for row in rows if source_allowed(agent, _legacy_entry(row))]


def _legacy(miniflux_client, *, job_id=None):
    store = SummaryStore(config.storage.path)
    if job_id:
        store.update_job(job_id, status="running")
    entries = _filter_legacy_entries(_read_legacy_entries())
    if not entries:
        if job_id:
            store.update_job(job_id, status="completed", processed_count=0)
        return []
    rendered = render_ai_news_input(config.ai_news_input, entries)
    greeting_prompt = config.ai_news_prompts.get("greeting")
    greeting = (
        get_ai_result(greeting_prompt, time.strftime("%B %d, %Y at %I:%M %p"))
        if greeting_prompt
        else None
    )
    summary_block = get_ai_result(config.ai_news_prompts["summary_block"], rendered)
    source = (
        summary_block if config.ai_news_use_summary_block_as_summary_input else rendered
    )
    summary = get_ai_result(config.ai_news_prompts["summary"], source)
    content = "\n\n".join(
        filter(
            None,
            [greeting, "### 🌐Summary\n" + summary, "### 📝News\n" + summary_block],
        )
    )
    with open("ai_news.json", "w", encoding="utf8") as f:
        json.dump(content, f, indent=4, ensure_ascii=False)
    _refresh(miniflux_client)
    # Legacy one-shot state remains for installations with batching disabled.
    with open("entries.json", "w", encoding="utf8") as f:
        json.dump([], f, indent=4, ensure_ascii=False)
    if job_id:
        store.update_job(job_id, status="completed", processed_count=len(entries))
    return content


def _legacy_sources(entry_ids):
    rows = _filter_legacy_entries(_read_legacy_entries())
    wanted = {str(entry_id) for entry_id in entry_ids or []}
    sources = []
    for row in rows:
        entry_id = str(row.get("entry_id", row.get("id", "")))
        if wanted and entry_id not in wanted:
            continue
        sources.append(
            {
                "entry_id": entry_id,
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "category": row.get("category", ""),
                "datetime": row.get("datetime", row.get("created_at", "")),
                "content": row.get("content", ""),
            }
        )
    return sources


def _eligible_summary_ids(miniflux_client, rows, source_entries=None):
    agent = config.agents.get(config.ai_news_batching.summary_agent)
    known = {
        str(entry["id"]): entry
        for entry in source_entries or []
        if entry.get("id") is not None
    }
    missing_ids = [
        str(row["entry_id"]) for row in rows if str(row["entry_id"]) not in known
    ]
    unavailable = 0

    def fetch(entry_id):
        try:
            return entry_id, miniflux_client.get_entry(int(entry_id))
        except Exception:
            return entry_id, None

    if missing_ids:
        workers = min(config.ai_news_batching.max_workers, len(missing_ids))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for entry_id, entry in executor.map(fetch, missing_ids):
                if entry is None:
                    unavailable += 1
                else:
                    known[entry_id] = entry

    eligible = {
        str(row["entry_id"])
        for row in rows
        if str(row["entry_id"]) in known
        and source_allowed(agent, known[str(row["entry_id"])])
    }
    logger.info(
        "Daily news source filter candidates=%s eligible=%s unavailable=%s",
        len(rows),
        len(eligible),
        unavailable,
    )
    return eligible


def _load_sources(miniflux_client, entry_ids, source_entries=None):
    store = SummaryStore(config.storage.path)
    settings = config.ai_news_batching
    if settings.source == "raw_entries":
        return _legacy_sources(entry_ids)[: settings.max_entries]
    rows = store.list_summaries(
        entry_ids=entry_ids,
        limit=settings.max_entries,
        agent_name=settings.summary_agent,
    )
    eligible_ids = _eligible_summary_ids(miniflux_client, rows, source_entries)
    summaries = [
        {
            "entry_id": str(row["entry_id"]),
            "title": row["title"],
            "url": row["url"],
            "category": row["category"],
            "datetime": row["published_at"],
            "content": row["summary_markdown"],
        }
        for row in rows
        if str(row["entry_id"]) in eligible_ids
    ]
    if settings.source != "prefer_summaries":
        return summaries
    covered = {item["entry_id"] for item in summaries}
    return (
        summaries
        + [row for row in _legacy_sources(entry_ids) if row["entry_id"] not in covered][
            : max(0, settings.max_entries - len(summaries))
        ]
    )


def _parse_object(raw, key):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get(key), list) else None


def _map_chunk(chunk):
    payload = json.dumps(
        {
            "entries": [
                {key: value for key, value in item.items() if key != "token_count"}
                for item in chunk
            ]
        },
        ensure_ascii=False,
    )
    prompt = "Return JSON object with stories list. Each story needs headline, category, kind, importance, summary, why_it_matters, source_entry_ids, source_urls, confidence. Preserve source IDs and URLs; no invented facts."
    data = _parse_object(get_ai_json_result(prompt, payload), "stories")
    if not data:
        raise ValueError("invalid daily map response")
    # Accept only output traceable to this chunk.
    allowed_ids = {
        str(i)
        for item in chunk
        for i in item.get("source_entry_ids", [item.get("entry_id")])
    }
    allowed_urls = {
        url for item in chunk for url in item.get("source_urls", [item.get("url")])
    }
    data["stories"] = [
        story
        for story in data["stories"]
        if isinstance(story, dict)
        and set(map(str, story.get("source_entry_ids", []))) <= allowed_ids
        and set(story.get("source_urls", [])) <= allowed_urls
    ]
    return data["stories"]


def _reduce(stories):
    payload = json.dumps({"stories": stories}, ensure_ascii=False)
    if (
        count_tokens(payload) > config.ai_news_batching.reduce_max_input_tokens
        and len(stories) > 1
    ):
        chunks = pack_items(
            [
                {
                    "story": story,
                    "token_count": count_tokens(json.dumps(story, ensure_ascii=False)),
                }
                for story in stories
            ],
            size=config.ai_news_batching.chunk_size,
            max_input_tokens=config.ai_news_batching.reduce_max_input_tokens,
        )
        flattened = []
        for chunk in chunks:
            intermediate = json.dumps(
                {"stories": [item["story"] for item in chunk]}, ensure_ascii=False
            )
            prompt = "Return JSON object with a bounded stories list. Preserve every supplied source ID and URL."
            result = _parse_object(get_ai_json_result(prompt, intermediate), "stories")
            if not result:
                raise ValueError("invalid intermediate reduce response")
            flattened.extend(result["stories"])
        return _reduce(flattened)
    prompt = "Return JSON daily report with overview list, sections list, opinions object, and watchlist list. Use only supplied source IDs/URLs."
    data = _parse_object(
        get_ai_json_result(
            prompt, payload, max_output_tokens=config.ai_news_batching.max_output_tokens
        ),
        "sections",
    )
    if not data:
        raise ValueError("invalid daily reduce response")
    return data


def _batched(miniflux_client, *, entry_ids=None, source_entries=None, job_id=None):
    store = SummaryStore(config.storage.path)
    if job_id:
        store.update_job(job_id, status="running")
    sources = _load_sources(miniflux_client, entry_ids, source_entries)
    if not sources:
        if job_id:
            store.update_job(job_id, status="completed")
        return None
    selected = (
        deduplicate_entries(sources, config.ai_news_batching.similarity_threshold)
        if config.ai_news_batching.deduplicate
        else sources
    )
    items = [
        {**item, "token_count": count_tokens(json.dumps(item, ensure_ascii=False))}
        for item in selected
    ]
    chunks = pack_items(
        items,
        size=config.ai_news_batching.chunk_size,
        max_input_tokens=config.ai_news_batching.chunk_max_input_tokens,
    )
    stories, failures = [], 0
    for chunk in chunks:
        try:
            stories.extend(_map_chunk(chunk))
        except Exception:
            failures += 1
    if failures and not config.ai_news_batching.publish_partial:
        raise ValueError("daily map stage failed")
    report = _reduce(stories)
    if failures:
        report.setdefault("overview", []).insert(
            0, "Warning: some source groups could not be processed."
        )
    content = render_daily_news(report, config.ai_news_output)
    source_ids = list(
        dict.fromkeys(
            str(i) for story in stories for i in story.get("source_entry_ids", [])
        )
    )
    report_id = str(uuid4())
    if job_id is None:
        job_id = store.create_job(
            "daily_news", len(sources), {"entry_ids": entry_ids or []}
        )
    store.save_daily_report(
        DailyReport(
            report_id,
            job_id,
            "Newsᴬᴵ for you",
            content,
            source_ids,
            config.llm_model or "",
        )
    )
    store.cleanup(
        summary_retention_days=config.storage.summary_retention_days,
        report_retention_count=config.storage.report_retention_count,
        job_retention_days=config.storage.job_retention_days,
    )
    store.update_job(
        job_id,
        status="partial" if failures else "completed",
        processed_count=len(sources),
        failed_count=failures,
    )
    _refresh(miniflux_client)
    return report_id


def generate_daily_news(
    miniflux_client, *, entry_ids=None, source_entries=None, job_id=None
):
    logger.info("Generating daily news")
    try:
        if config.ai_news_batching.enabled:
            return _batched(
                miniflux_client,
                entry_ids=entry_ids,
                source_entries=source_entries,
                job_id=job_id,
            )
        return _legacy(miniflux_client, job_id=job_id)
    except Exception as exc:
        logger.error("Daily news generation failed: %s", type(exc).__name__)
        if job_id:
            SummaryStore(config.storage.path).update_job(
                job_id, status="failed", error="daily news generation failed"
            )
        return None
