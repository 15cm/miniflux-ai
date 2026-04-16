import concurrent.futures

import miniflux
from flask import jsonify, request

from common.config import Config
from common.logger import logger
from core.reprocess_utils import fetch_entries_by_scope, run_process
from myapp import app

config = Config()
miniflux_client = miniflux.Client(config.miniflux_base_url, api_key=config.miniflux_api_key)


@app.route('/api/reprocess', methods=['POST'])
def reprocess():
    """Force reprocess entries.

    POST /api/reprocess
    Body (JSON):
      { "scope": "unread" }
      { "scope": "all" }
      { "scope": "last_n", "n": 100 }
      { "scope": "duration", "duration": "1h" }   # units: m, h, d
    """
    body = request.get_json(silent=True) or {}
    entries, err = fetch_entries_by_scope(miniflux_client, body)
    if err:
        return jsonify({'status': 'error', 'message': err[0]}), err[1]

    count = len(entries)
    logger.info(f'Reprocess triggered: scope={body.get("scope")}, entries={count}')

    if entries:
        concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(run_process, miniflux_client, entries)

    return jsonify({'status': 'ok', 'queued': count})
