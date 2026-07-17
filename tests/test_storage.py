from core.storage import EntrySummary, SummaryStore


def test_summary_cache_and_job_lifecycle(tmp_path):
    store = SummaryStore(str(tmp_path / "data" / "store.db"))
    store.initialize()
    summary = EntrySummary(
        1,
        "summary",
        "source",
        "title",
        "https://x",
        "cat",
        "2026-01-01",
        "text",
        None,
        "model",
        "prompt",
    )
    store.upsert_summary(summary)
    assert (
        store.get_current_summary(1, "summary", "source", "prompt", "model")[
            "summary_markdown"
        ]
        == "text"
    )
    assert store.get_current_summary(1, "summary", "changed", "prompt", "model") is None
    job = store.create_job("test", 1, {"quote": "' OR 1=1"})
    store.update_job(job, status="running")
    store.update_job(job, status="completed", processed_count=1)
    assert store.get_job(job)["status"] == "completed"
