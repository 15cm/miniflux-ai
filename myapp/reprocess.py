import concurrent.futures
import miniflux
from flask import jsonify, request
from common.config import Config
from common.logger import logger
from core.reprocess_utils import fetch_entries_by_scope, run_process
from core.storage import SummaryStore
from myapp import app
from myapp.security import require_bearer

config = Config()
miniflux_client = miniflux.Client(
    config.miniflux_base_url, api_key=config.miniflux_api_key
)


@app.route("/api/reprocess", methods=["POST"])
def reprocess():
    denied = require_bearer(config.api_protect_manual_endpoints)
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    entries, err = fetch_entries_by_scope(miniflux_client, body)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]
    store = SummaryStore(config.storage.path)
    job_id = store.create_job("reprocess", len(entries), {"scope": body})
    logger.info("Reprocess queued entries=%s job=%s", len(entries), job_id)
    if entries:
        concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(
            run_process, miniflux_client, entries, job_id=job_id
        )
    else:
        store.update_job(job_id, status="completed")
    return jsonify({"status": "queued", "job_id": job_id, "queued": len(entries)})
