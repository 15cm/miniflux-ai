import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

from common.config import LLMBatchConfig

process_module = importlib.import_module("core.process_entries")


def _entry(entry_id, category="Tech", site_url="https://allowed.example/"):
    return {
        "id": entry_id,
        "title": f"Entry {entry_id}",
        "content": "article",
        "url": f"https://article.example/{entry_id}",
        "created_at": "2026-09-26T00:00:00Z",
        "feed": {
            "site_url": site_url,
            "category": {"title": category},
        },
        "tags": [],
    }


def _config(tmp_path, *, batching):
    agent = {
        "title": "AI summary",
        "style_block": False,
        "input": "{{ content }}",
        "prompt": "summarize",
        "deny_list": ["https://blocked.example/*"],
        "category_deny_list": ["Private/*"],
    }
    return SimpleNamespace(
        agents={"summary": agent},
        storage=SimpleNamespace(path=str(tmp_path / "summary.db")),
        llm_model="model",
        get_agent_batching=lambda _name: LLMBatchConfig(enabled=batching),
        get_agent_output=lambda _name: None,
    )


def test_denied_entry_never_reaches_legacy_llm_or_miniflux(tmp_path, monkeypatch):
    monkeypatch.setattr(process_module, "config", _config(tmp_path, batching=False))
    llm = MagicMock(side_effect=AssertionError("denied entry reached LLM"))
    monkeypatch.setattr(process_module, "get_ai_result", llm)
    client = MagicMock()

    stats = process_module.process_entries(client, [_entry(1, category="Private/Work")])

    assert stats.successes == 0
    llm.assert_not_called()
    client.update_entry.assert_not_called()


def test_denied_entry_never_reaches_batch_cache_or_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(process_module, "config", _config(tmp_path, batching=True))
    cache = MagicMock(side_effect=AssertionError("denied entry reached cache"))
    llm = MagicMock(side_effect=AssertionError("denied entry reached LLM"))
    monkeypatch.setattr(process_module.SummaryStore, "get_current_summary", cache)
    monkeypatch.setattr(process_module, "get_ai_json_result", llm)
    client = MagicMock()

    stats = process_module.process_entries(
        client, [_entry(1, site_url="https://blocked.example/feed")]
    )

    assert stats.batches == 0
    cache.assert_not_called()
    llm.assert_not_called()
    client.update_entry.assert_not_called()


def test_mixed_legacy_entries_only_process_allowed_source(tmp_path, monkeypatch):
    monkeypatch.setattr(process_module, "config", _config(tmp_path, batching=False))
    llm = MagicMock(return_value="summary")
    monkeypatch.setattr(process_module, "get_ai_result", llm)
    monkeypatch.setattr(process_module, "_append_legacy_summary", MagicMock())
    client = MagicMock()

    stats = process_module.process_entries(
        client,
        [_entry(1), _entry(2, category="Private/Work")],
    )

    assert stats.successes == 1
    llm.assert_called_once()
    client.update_entry.assert_called_once()
    assert client.update_entry.call_args.args[0] == 1
