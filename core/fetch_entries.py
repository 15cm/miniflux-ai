MAX_PAGE_SIZE = 1000


def fetch_entries_paginated(miniflux_client, *, max_entries=None, **params):
    """Fetch entries without exceeding Miniflux's per-request limit."""
    entries = []
    offset = int(params.pop("offset", 0))

    while max_entries is None or len(entries) < max_entries:
        remaining = (
            MAX_PAGE_SIZE
            if max_entries is None
            else min(MAX_PAGE_SIZE, max_entries - len(entries))
        )
        result = miniflux_client.get_entries(
            limit=remaining,
            offset=offset,
            **params,
        )
        page = result.get("entries") or []
        entries.extend(page)
        offset += len(page)

        total = result.get("total")
        if (
            not page
            or len(page) < remaining
            or (isinstance(total, int) and offset >= total)
        ):
            break

    return entries
