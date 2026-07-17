import hashlib
import hmac
import concurrent.futures
import miniflux
from flask import abort, jsonify, request
from common.config import Config
from core.process_entries import process_entries
from core.storage import SummaryStore
from myapp import app

config = Config()
miniflux_client = miniflux.Client(
    config.miniflux_base_url, api_key=config.miniflux_api_key
)


@app.route("/api/miniflux-ai", methods=["POST"])
def miniflux_ai():
    secret = config.miniflux_webhook_secret
    payload = request.get_data()
    signature = request.headers.get("X-Miniflux-Signature", "")
    if not secret or not hmac.compare_digest(
        hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest(), signature
    ):
        abort(403)
    data = request.get_json(silent=True) or {}
    entries = data.get("entries", [])
    for entry in entries:
        entry["feed"] = data.get("feed", entry.get("feed", {}))
    job_id = SummaryStore(config.storage.path).create_job("webhook", len(entries), {})
    concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(
        process_entries, miniflux_client, entries, job_id=job_id
    )
    return jsonify({"status": "queued", "job_id": job_id, "queued": len(entries)})
