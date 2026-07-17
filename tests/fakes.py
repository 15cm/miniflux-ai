class FakeLLM:
    """Deterministic in-process provider used by batch tests and benchmarks."""

    def __init__(self, responses=None, failures=None):
        self.responses = list(responses or [])
        self.failures = list(failures or [])
        self.requests = []

    def complete(self, *, prompt, request, **kwargs):
        self.requests.append({"prompt": prompt, "request": request, **kwargs})
        if self.failures:
            failure = self.failures.pop(0)
            if failure:
                raise failure
        return self.responses.pop(0) if self.responses else '{"entries": []}'

    @property
    def calls(self):
        return len(self.requests)


def make_large_entries(count=100):
    """Deterministic 100-entry benchmark fixture without a huge checked-in file."""
    return [
        {
            "id": index,
            "title": f"Story {index % 20}",
            "content": "article " * (20 + index % 5),
            "url": f"https://example.test/{index}",
            "feed": {
                "site_url": "https://example.test",
                "category": {"title": f"Category {index % 4}"},
            },
            "created_at": f"2026-07-17T{index % 24:02d}:00:00Z",
        }
        for index in range(count)
    ]
