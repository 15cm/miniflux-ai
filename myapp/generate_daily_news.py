import concurrent.futures

import miniflux
from flask import jsonify

from common.config import Config
from common.logger import logger
from core.generate_daily_news import generate_daily_news
from myapp import app

config = Config()
miniflux_client = miniflux.Client(config.miniflux_base_url, api_key=config.miniflux_api_key)


@app.route('/api/generate-daily-news', methods=['POST'])
def trigger_generate_daily_news():
    logger.info('Manual daily news generation triggered via API')
    concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(generate_daily_news, miniflux_client)
    return jsonify({'status': 'ok'})
