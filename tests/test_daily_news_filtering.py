import importlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from common.config import AINewsBatchConfig, StorageConfig
from core.storage import EntrySummary, SummaryStore

news_module = importlib.import_module("core.generate_daily_news")


def _agent():
    return {
        "deny_list": ["https://blocked.example/*"],
        "category_deny_list": ["Private/*"],
    }


def _config(tmp_path, *, batching=True, source="entry_summaries"):
    return SimpleNamespace(
        agents={"summary": _agent()},
        ai_news_batching=AINewsBatchConfig(
            enabled=batching,
            source=source,
            summary_agent="summary",
            max_entries=10,
        ),
        ai_news_input="{{ entries }}",
        ai_news_prompts={"summary": "summary", "summary_block": "summary block"},
        ai_news_use_summary_block_as_summary_input=False,
        ai_news_output=SimpleNamespace(),
        storage=StorageConfig(path=str(tmp_path / "summary.db")),
        llm_model="model",
    )


def _miniflux_entry(entry_id, category="Tech", site_url="https://allowed.example/"):
    return {
        "id": entry_id,
        "content": "article",
        "feed": {
            "site_url": site_url,
            "category": {"title": category},
        },
    }


def _save_summary(path, entry_id):
    store = SummaryStore(path)
    store.initialize()
    store.upsert_summary(
        EntrySummary(
            entry_id,
            "summary",
            "source",
            "title",
            f"https://article.example/{entry_id}",
            "Private/Work",
            "2026-09-26T00:00:00Z",
            "cached summary",
            None,
            "model",
            "prompt",
        )
    )


def test_stale_denied_sqlite_summary_never_reaches_daily_llm(tmp_path, monkeypatch):
    config = _config(tmp_path)
    monkeypatch.setattr(news_module, "config", config)
    _save_summary(config.storage.path, 1)
    client = MagicMock()
    client.get_entry.return_value = _miniflux_entry(1, category="Private/Work")
    map_call = MagicMock(side_effect=AssertionError("denied source reached map LLM"))
    reduce_call = MagicMock(
        side_effect=AssertionError("denied source reached reduce LLM")
    )
    monkeypatch.setattr(news_module, "_map_chunk", map_call)
    monkeypatch.setattr(news_module, "_reduce", reduce_call)

    result = news_module._batched(client)

    assert result is None
    map_call.assert_not_called()
    reduce_call.assert_not_called()
    client.refresh_feed.assert_not_called()


def test_failed_metadata_lookup_fails_closed(tmp_path, monkeypatch):
    config = _config(tmp_path)
    monkeypatch.setattr(news_module, "config", config)
    _save_summary(config.storage.path, 1)
    client = MagicMock()
    client.get_entry.side_effect = RuntimeError("unavailable")
    monkeypatch.setattr(
        news_module,
        "_map_chunk",
        MagicMock(side_effect=AssertionError("unknown source reached LLM")),
    )

    assert news_module._batched(client) is None


def test_legacy_rows_missing_site_url_fail_closed(tmp_path, monkeypatch):
    config = _config(tmp_path, batching=False)
    monkeypatch.setattr(news_module, "config", config)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "entries.json").write_text(
        json.dumps(
            [
                {
                    "entry_id": 1,
                    "category": "Tech",
                    "content": "old summary",
                }
            ]
        )
    )
    llm = MagicMock(side_effect=AssertionError("unverifiable source reached LLM"))
    monkeypatch.setattr(news_module, "get_ai_result", llm)

    assert news_module._legacy(MagicMock()) == []
    llm.assert_not_called()


def test_explicit_allowed_metadata_avoids_refetch(tmp_path, monkeypatch):
    config = _config(tmp_path)
    monkeypatch.setattr(news_module, "config", config)
    _save_summary(config.storage.path, 1)
    client = MagicMock()

    sources = news_module._load_sources(
        client,
        ["1"],
        [_miniflux_entry(1)],
    )

    assert [source["entry_id"] for source in sources] == ["1"]
    client.get_entry.assert_not_called()


def test_raw_legacy_sources_apply_current_rules(tmp_path, monkeypatch):
    config = _config(tmp_path, source="raw_entries")
    monkeypatch.setattr(news_module, "config", config)
    monkeypatch.chdir(tmp_path)
    rows = [
        {
            "entry_id": 1,
            "category": "Tech",
            "site_url": "https://allowed.example/",
            "content": "allowed",
        },
        {
            "entry_id": 2,
            "category": "Private/Work",
            "site_url": "https://blocked.example/feed",
            "content": "denied",
        },
    ]
    (tmp_path / "entries.json").write_text(json.dumps(rows))

    sources = news_module._load_sources(MagicMock(), None)

    assert [source["entry_id"] for source in sources] == ["1"]
