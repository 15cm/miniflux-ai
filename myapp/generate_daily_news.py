import concurrent.futures
import json
import miniflux
from flask import jsonify, request
from common.config import Config
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
    if not config.ai_news_batching.enabled:
        _build_entries_json(entries)
    generate_daily_news(
        miniflux_client,
        entry_ids=[str(entry["id"]) for entry in entries],
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
