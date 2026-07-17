import time
from common.logger import logger
from core.process_entries import process_entries


def fetch_unread_entries(config, miniflux_client):
    result = miniflux_client.get_entries(status=["unread"], limit=10000)
    entries = result["entries"]
    if not entries:
        logger.info("No new entries")
        return None
    start = time.time()
    stats = process_entries(miniflux_client, entries)
    if time.time() - start >= 3:
        logger.info("Done entries=%s calls=%s", stats.entries, stats.calls)
    return stats
