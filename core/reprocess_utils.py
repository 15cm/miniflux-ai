import re
import time
import traceback
import concurrent.futures

from common.config import Config
from common.logger import logger
from core.process_entries import process_entry

config = Config()


def parse_duration(duration_str):
    """Parse duration string like '30m', '2h', '1d' into seconds."""
    match = re.fullmatch(r'(\d+)([mhd])', duration_str.strip())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    return value * {'m': 60, 'h': 3600, 'd': 86400}[unit]


def fetch_entries_by_scope(miniflux_client, body):
    """Fetch entries based on scope params. Returns (entries, error_response).

    body keys: scope, n, duration
    On error returns (None, (message, http_status)).
    """
    scope = body.get('scope')

    if scope == 'unread':
        result = miniflux_client.get_entries(status=['unread'], limit=10000)
        return result['entries'], None

    elif scope == 'all':
        result = miniflux_client.get_entries(limit=10000)
        return result['entries'], None

    elif scope == 'last_n':
        n = body.get('n')
        if not isinstance(n, int) or n <= 0:
            return None, ('n must be a positive integer', 400)
        result = miniflux_client.get_entries(limit=n, order='published_at', direction='desc')
        return result['entries'], None

    elif scope == 'duration':
        duration_str = body.get('duration', '')
        seconds = parse_duration(str(duration_str))
        if seconds is None:
            return None, ('duration must be like "30m", "2h", "1d"', 400)
        after_ts = int(time.time()) - seconds
        result = miniflux_client.get_entries(limit=10000, after=after_ts)
        return result['entries'], None

    else:
        return None, ('scope must be one of: unread, all, last_n, duration', 400)


def run_process(miniflux_client, entries):
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.llm_max_workers) as executor:
        futures = [
            executor.submit(process_entry, miniflux_client, entry)
            for entry in entries
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error('reprocess exception: %s' % e)
