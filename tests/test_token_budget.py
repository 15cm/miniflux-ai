from core.token_budget import count_tokens, pack_items, truncate_tokens


def test_pack_preserves_order_and_caps_size():
    items = [{"id": str(index), "token_count": 2} for index in range(5)]
    assert [
        [item["id"] for item in batch]
        for batch in pack_items(items, size=2, max_input_tokens=20)
    ] == [["0", "1"], ["2", "3"], ["4"]]


def test_pack_splits_token_budget():
    items = [{"id": "a", "token_count": 6}, {"id": "b", "token_count": 6}]
    assert len(pack_items(items, size=8, max_input_tokens=10)) == 2


def test_unicode_truncate_is_valid_text():
    text, truncated = truncate_tokens("中文" * 100, 10)
    assert truncated and text and count_tokens(text) <= 10
