import json
import time

from common import logger
from common.config import Config
from core.get_ai_result import get_ai_result
from core.render_input import render_ai_news_input

config = Config()

def generate_daily_news(miniflux_client):
    logger.info('Generating daily news')
    # fetch entries.json
    try:
        with open('entries.json', 'r') as f:
            entries = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning('entries.json not found or corrupted, skipping daily news generation')
        return []

    if not entries:
        logger.info('No entries to generate daily news')
        return []

    try:
        rendered_input = render_ai_news_input(config.ai_news_input, entries)

        # greeting (optional)
        greeting_prompt = config.ai_news_prompts.get('greeting')
        greeting = get_ai_result(greeting_prompt, time.strftime('%B %d, %Y at %I:%M %p')) if greeting_prompt else None
        # summary_block
        summary_block = get_ai_result(config.ai_news_prompts['summary_block'], rendered_input)
        # summary: use summary_block as input (old behavior) or rendered_input (new default)
        if config.ai_news_use_summary_block_as_summary_input:
            summary = get_ai_result(config.ai_news_prompts['summary'], summary_block)
        else:
            summary = get_ai_result(config.ai_news_prompts['summary'], rendered_input)

        parts = []
        if greeting:
            parts.append(greeting)
        parts.append('### 🌐Summary\n' + summary)
        parts.append('### 📝News\n' + summary_block)
        response_content = '\n\n'.join(parts)

        logger.info('Generated daily news successfully')

        with open('ai_news.json', 'w') as f:
            json.dump(response_content, f, indent=4, ensure_ascii=False)

        # trigger miniflux feed refresh
        feeds = miniflux_client.get_feeds()
        ai_news_feed_id = next((item['id'] for item in feeds if 'Newsᴬᴵ for you' in item['title']), None)

        if ai_news_feed_id:
            miniflux_client.refresh_feed(ai_news_feed_id)
            logger.debug('Successfully refreshed the ai_news feed in Miniflux!')

    except Exception as e:
        logger.error(f'Error generating daily news: {e}')

    finally:
        try:
            with open('entries.json', 'w') as f:
                json.dump([], f, indent=4, ensure_ascii=False)
            logger.info('Cleared entries.json')
        except Exception as e:
            logger.error(f'Failed to clear entries.json: {e}')
