import concurrent.futures
import re
import time
import traceback
from datetime import datetime, timezone

import miniflux
from flask import abort, jsonify, request

from common.config import Config
from common.logger import logger
from core.process_entries import process_entry
from myapp import app

config = Config()
miniflux_client = miniflux.Client(config.miniflux_base_url, api_key=config.miniflux_api_key)


def _check_auth():
    secret = config.miniflux_webhook_secret
    if not secret:
        return
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[len('Bearer '):]
        if token == secret:
            return
    abort(403)


def _parse_duration(duration_str):
    """Parse duration string like '30m', '2h', '1d' into seconds."""
    match = re.fullmatch(r'(\d+)([mhd])', duration_str.strip())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    return value * {'m': 60, 'h': 3600, 'd': 86400}[unit]


def _run_process(entries):
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.llm_max_workers) as executor:
        futures = [executor.submit(process_entry, miniflux_client, entry) for entry in entries]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error('reprocess exception: %s' % e)


@app.route('/api/reprocess', methods=['POST'])
def reprocess():
    """Force reprocess entries.

    POST /api/reprocess
    Authorization: Bearer <miniflux_webhook_secret>  (required if webhook secret is configured)

    Body (JSON):
      { "scope": "unread" }
      { "scope": "all" }
      { "scope": "last_n", "n": 100 }
      { "scope": "duration", "duration": "1h" }   # units: m, h, d
    """
    _check_auth()

    body = request.get_json(silent=True) or {}
    scope = body.get('scope')

    if scope == 'unread':
        result = miniflux_client.get_entries(status=['unread'], limit=10000)
        entries = result['entries']

    elif scope == 'all':
        result = miniflux_client.get_entries(limit=10000)
        entries = result['entries']

    elif scope == 'last_n':
        n = body.get('n')
        if not isinstance(n, int) or n <= 0:
            return jsonify({'status': 'error', 'message': 'n must be a positive integer'}), 400
        result = miniflux_client.get_entries(limit=n, order='published_at', direction='desc')
        entries = result['entries']

    elif scope == 'duration':
        duration_str = body.get('duration', '')
        seconds = _parse_duration(str(duration_str))
        if seconds is None:
            return jsonify({'status': 'error', 'message': 'duration must be like "30m", "2h", "1d"'}), 400
        after_ts = int(time.time()) - seconds
        result = miniflux_client.get_entries(limit=10000, after=after_ts)
        entries = result['entries']

    else:
        return jsonify({'status': 'error', 'message': 'scope must be one of: unread, all, last_n, duration'}), 400

    count = len(entries)
    logger.info(f'Reprocess triggered: scope={scope}, entries={count}')

    if entries:
        concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(_run_process, entries)

    return jsonify({'status': 'ok', 'queued': count})
