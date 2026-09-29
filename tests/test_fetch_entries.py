from unittest.mock import MagicMock

from core.fetch_entries import fetch_entries_paginated


def test_fetches_every_page_at_server_limit():
    client = MagicMock()
    client.get_entries.side_effect = [
        {"entries": list(range(1000)), "total": 2005},
        {"entries": list(range(1000, 2000)), "total": 2005},
        {"entries": list(range(2000, 2005)), "total": 2005},
    ]

    entries = fetch_entries_paginated(client, status=["unread"])

    assert len(entries) == 2005
    assert client.get_entries.call_args_list == [
        ((), {"limit": 1000, "offset": 0, "status": ["unread"]}),
        ((), {"limit": 1000, "offset": 1000, "status": ["unread"]}),
        ((), {"limit": 1000, "offset": 2000, "status": ["unread"]}),
    ]


def test_respects_max_entries_across_pages():
    client = MagicMock()
    client.get_entries.side_effect = [
        {"entries": list(range(1000)), "total": 5000},
        {"entries": list(range(1000, 1500)), "total": 5000},
    ]

    entries = fetch_entries_paginated(client, max_entries=1500)

    assert len(entries) == 1500
    client.get_entries.assert_called_with(limit=500, offset=1000)
