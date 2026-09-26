import concurrent.futures
import json
import miniflux
from flask import jsonify, request
from common.config import Config
from common.logger import logger
from core.entry_filter import source_allowed
from core.generate_daily_news import generate_daily_news
from core.reprocess_utils import fetch_entries_by_scope
from core.storage import SummaryStore
from myapp import app
from myapp.security import require_bearer

config = Config()
miniflux_client = miniflux.Client(
    config.miniflux_base_url, api_key=config.miniflux_api_key
)


def _build_entries_json(entries):
    data = [
        {
            "entry_id": e["id"],
            "datetime": e["created_at"],
            "category": e["feed"]["category"]["title"],
            "site_url": e["feed"].get("site_url"),
            "title": e["title"],
            "content": e["content"],
            "url": e["url"],
            "tags": e.get("tags", []),
        }
        for e in entries
    ]
    with open("entries.json", "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def _build_and_generate(entries, job_id=None):
    agent = config.agents.get(config.ai_news_batching.summary_agent)
    candidate_count = len(entries)
    entries = [entry for entry in entries if source_allowed(agent, entry)]
    logger.info(
        "Manual daily news source filter candidates=%s eligible=%s",
        candidate_count,
        len(entries),
    )
    if not config.ai_news_batching.enabled or config.ai_news_batching.source in {
        "raw_entries",
        "prefer_summaries",
    }:
        _build_entries_json(entries)
    generate_daily_news(
        miniflux_client,
        entry_ids=[str(entry["id"]) for entry in entries],
        source_entries=entries,
        job_id=job_id,
    )


@app.route("/api/generate-daily-news", methods=["POST"])
def trigger_generate_daily_news():
    denied = require_bearer(config.api_protect_manual_endpoints)
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    scope = body.get("scope")
    entries = None
    if scope:
        entries, err = fetch_entries_by_scope(miniflux_client, body)
        if err:
            return jsonify({"status": "error", "message": err[0]}), err[1]
    count = len(entries) if entries is not None else 0
    job_id = SummaryStore(config.storage.path).create_job(
        "daily_news", count, {"scope": body}
    )
    if entries is not None:
        concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(
            _build_and_generate, entries, job_id
        )
    else:
        concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(
            generate_daily_news, miniflux_client, job_id=job_id
        )
    return jsonify({"status": "queued", "job_id": job_id, "queued": count})
