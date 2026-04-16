import json
import concurrent.futures

import miniflux
from flask import jsonify, request

from common.config import Config
from common.logger import logger
from core.generate_daily_news import generate_daily_news
from core.reprocess_utils import fetch_entries_by_scope
from myapp import app

config = Config()
miniflux_client = miniflux.Client(config.miniflux_base_url, api_key=config.miniflux_api_key)


def _build_entries_json(entries):
    """Write fetched entries to entries.json for daily news generation."""
    data = [
        {
            'datetime': entry['created_at'],
            'category': entry['feed']['category']['title'],
            'title': entry['title'],
            'content': entry['content'],
            'url': entry['url'],
            'tags': entry.get('tags', []),
        }
        for entry in entries
    ]
    with open('entries.json', 'w') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f'Wrote {len(data)} entries to entries.json')


def _build_and_generate(entries):
    _build_entries_json(entries)
    generate_daily_news(miniflux_client)


@app.route('/api/generate-daily-news', methods=['POST'])
def trigger_generate_daily_news():
    """Trigger daily news generation, optionally fetching entries by scope first.

    POST /api/generate-daily-news
    Body (JSON, optional):
      {}                                           # generate from existing entries.json
      { "scope": "unread" }
      { "scope": "all" }
      { "scope": "last_n", "n": 100 }
      { "scope": "duration", "duration": "1h" }   # units: m, h, d
    """
    body = request.get_json(silent=True) or {}
    scope = body.get('scope')

    if scope:
        entries, err = fetch_entries_by_scope(miniflux_client, body)
        if err:
            return jsonify({'status': 'error', 'message': err[0]}), err[1]

        count = len(entries)
        logger.info(f'Generate daily news triggered: scope={scope}, entries={count}')

        concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(
            _build_and_generate, entries
        )
        return jsonify({'status': 'ok', 'queued': count})

    logger.info('Manual daily news generation triggered via API')
    concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(generate_daily_news, miniflux_client)
    return jsonify({'status': 'ok'})
