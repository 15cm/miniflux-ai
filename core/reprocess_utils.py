import re
import time
from common.config import Config
from common.logger import logger
from core.fetch_entries import fetch_entries_paginated
from core.process_entries import process_entries

config = Config()


def parse_duration(duration_str):
    match = re.fullmatch(r"(\d+)([mhd])", duration_str.strip())
    if not match:
        return None
    return int(match.group(1)) * {"m": 60, "h": 3600, "d": 86400}[match.group(2)]


def fetch_entries_by_scope(miniflux_client, body):
    scope = body.get("scope")
    if scope == "unread":
        return (
            fetch_entries_paginated(
                miniflux_client, max_entries=10000, status=["unread"]
            ),
            None,
        )
    if scope == "all":
        return fetch_entries_paginated(miniflux_client, max_entries=10000), None
    if scope == "last_n":
        n = body.get("n")
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            return None, ("n must be a positive integer", 400)
        return (
            fetch_entries_paginated(
                miniflux_client,
                max_entries=n,
                order="published_at",
                direction="desc",
            ),
            None,
        )
    if scope == "duration":
        seconds = parse_duration(str(body.get("duration", "")))
        if seconds is None:
            return None, ('duration must be like "30m", "2h", "1d"', 400)
        return (
            fetch_entries_paginated(
                miniflux_client,
                max_entries=10000,
                after=int(time.time()) - seconds,
            ),
            None,
        )
    return None, ("scope must be one of: unread, all, last_n, duration", 400)


def run_process(miniflux_client, entries, *, job_id=None):
    try:
        return process_entries(miniflux_client, entries, job_id=job_id)
    except Exception as exc:
        logger.error("reprocess failed: %s", type(exc).__name__)
        raise
