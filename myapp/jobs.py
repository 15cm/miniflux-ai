from flask import jsonify
from common.config import Config
from core.storage import SummaryStore
from myapp import app
from myapp.security import require_bearer


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    config = Config()
    denied = require_bearer(config.api_protect_job_endpoint)
    if denied:
        return denied
    job = SummaryStore(config.storage.path).get_job(job_id)
    if job is None:
        return jsonify({"status": "error", "message": "job not found"}), 404
    job.pop("metadata_json", None)
    return jsonify(job)
