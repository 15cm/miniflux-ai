"""Validated application configuration.

Old keys remain exposed as attributes so an installation can enable batching
incrementally without changing its existing configuration file.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from yaml import safe_load


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LLMBatchConfig:
    enabled: bool = False
    size: int = 8
    max_input_tokens: int = 60000
    max_entry_tokens: int = 8000
    max_workers: int = 2
    retries: int = 2
    retry_base_seconds: float = 1.0
    retry_max_seconds: float = 20.0
    retry_split: bool = True
    fallback_to_individual: bool = True
    response_format: str = "json_object"
    reserve_output_tokens_per_entry: int = 300
    max_output_tokens_per_entry: int = 300


@dataclass(frozen=True)
class AINewsBatchConfig:
    enabled: bool = False
    source: str = "entry_summaries"
    summary_agent: str = "summary"
    max_entries: int = 200
    chunk_size: int = 20
    chunk_max_input_tokens: int = 50000
    max_workers: int = 2
    reduce_max_input_tokens: int = 60000
    max_output_tokens: int = 2500
    deduplicate: bool = True
    similarity_threshold: float = 0.85
    publish_partial: bool = False
    missing_summary: str = "summarize_inline"


@dataclass(frozen=True)
class OutputConfig:
    language: str | None = None
    heading: str = "Key points"
    max_bullets: int = 3
    include_why_it_matters: bool = True
    include_sources: bool = False
    overview_max_sentences: int = 4
    max_sections: int = 8
    max_items_per_section: int = 5
    max_sources_per_item: int = 3
    include_overview: bool = True
    include_opinions: bool = True
    include_watchlist: bool = True


@dataclass(frozen=True)
class StorageConfig:
    backend: str = "sqlite"
    path: str = "/app/data/miniflux-ai.db"
    summary_retention_days: int = 30
    report_retention_count: int = 30
    job_retention_days: int = 14


def _mapping(value: Any, key: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be a mapping")
    return value


def _bool(value: Any, key: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be a boolean")
    return value


def _int(
    value: Any, key: str, default: int, minimum: int, maximum: int | None = None
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{key} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        upper = f"..{maximum}" if maximum is not None else "+"
        raise ConfigError(f"{key} must be in range {minimum}{upper}")
    return value


def _number(value: Any, key: str, default: float, minimum: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key} must be a number")
    if value < minimum:
        raise ConfigError(f"{key} must be at least {minimum}")
    return float(value)


class Config:
    def __init__(self, path: str = "config.yml"):
        file_path = Path(path)
        self._config_file_exists = file_path.exists()
        if self._config_file_exists:
            with file_path.open(encoding="utf8") as config_file:
                self.c = safe_load(config_file) or {}
        else:
            # Makes imports and an empty fresh deployment deterministic. Required
            # service credentials still fail at their actual use site.
            self.c = {}
        self.c = _mapping(self.c, "config")
        self.log_level = self.c.get("log_level", "INFO")

        miniflux = _mapping(self.c.get("miniflux"), "miniflux")
        self.miniflux_base_url = miniflux.get("base_url")
        self.miniflux_api_key = miniflux.get("api_key")
        self.miniflux_webhook_secret = miniflux.get("webhook_secret")
        self.miniflux_schedule_interval = miniflux.get("schedule_interval")

        llm = _mapping(self.c.get("llm"), "llm")
        self.llm_provider = llm.get("provider", "openai")
        self.llm_base_url = llm.get("base_url")
        self.llm_api_key = llm.get("api_key")
        self.llm_model = llm.get("model")
        self.llm_max_length = llm.get("max_length")
        self.llm_timeout = llm.get("timeout", 60)
        self.llm_max_workers = llm.get("max_workers", 4)
        self.llm_RPM = llm.get("RPM", 1000)
        self.llm_batching = self._parse_llm_batch(
            _mapping(llm.get("batching"), "llm.batching")
        )

        news = _mapping(self.c.get("ai_news"), "ai_news")
        self.ai_news_url = news.get("url")
        self.ai_news_schedule = news.get("schedule")
        self.ai_news_prompts = news.get("prompts") or {}
        self.ai_news_input = news.get("input") or (
            '{\n{%- for category, group in entries | groupby("category") %}\n  "{{ category }}": {{ group | list | tojson }}{% if not loop.last %},{% endif %}\n{%- endfor %}\n}'
        )
        self.ai_news_use_summary_block_as_summary_input = _bool(
            news.get("use_summary_block_as_summary_input"),
            "ai_news.use_summary_block_as_summary_input",
            False,
        )
        self.ai_news_batching = self._parse_news_batch(
            _mapping(news.get("batching"), "ai_news.batching")
        )
        self.ai_news_output = self._parse_output(
            _mapping(news.get("output"), "ai_news.output"), OutputConfig()
        )

        self.storage = self._parse_storage(_mapping(self.c.get("storage"), "storage"))
        api = _mapping(self.c.get("api"), "api")
        self.api_bearer_token = api.get("bearer_token")
        self.api_protect_manual_endpoints = _bool(
            api.get("protect_manual_endpoints"), "api.protect_manual_endpoints", False
        )
        self.api_protect_job_endpoint = _bool(
            api.get("protect_job_endpoint"), "api.protect_job_endpoint", False
        )

        self.agents = _mapping(self.c.get("agents"), "agents")
        self._validate_agents()

    def _parse_llm_batch(self, raw: dict[str, Any]) -> LLMBatchConfig:
        defaults = LLMBatchConfig()
        value = LLMBatchConfig(
            enabled=_bool(raw.get("enabled"), "llm.batching.enabled", defaults.enabled),
            size=_int(raw.get("size"), "llm.batching.size", defaults.size, 1, 100),
            max_input_tokens=_int(
                raw.get("max_input_tokens"),
                "llm.batching.max_input_tokens",
                defaults.max_input_tokens,
                1000,
            ),
            max_entry_tokens=_int(
                raw.get("max_entry_tokens"),
                "llm.batching.max_entry_tokens",
                defaults.max_entry_tokens,
                100,
            ),
            max_workers=_int(
                raw.get("max_workers"),
                "llm.batching.max_workers",
                defaults.max_workers,
                1,
                32,
            ),
            retries=_int(
                raw.get("retries"), "llm.batching.retries", defaults.retries, 0, 10
            ),
            retry_base_seconds=_number(
                raw.get("retry_base_seconds"),
                "llm.batching.retry_base_seconds",
                defaults.retry_base_seconds,
                0,
            ),
            retry_max_seconds=_number(
                raw.get("retry_max_seconds"),
                "llm.batching.retry_max_seconds",
                defaults.retry_max_seconds,
                0,
            ),
            retry_split=_bool(
                raw.get("retry_split"), "llm.batching.retry_split", defaults.retry_split
            ),
            fallback_to_individual=_bool(
                raw.get("fallback_to_individual"),
                "llm.batching.fallback_to_individual",
                defaults.fallback_to_individual,
            ),
            response_format=raw.get("response_format", defaults.response_format),
            reserve_output_tokens_per_entry=_int(
                raw.get("reserve_output_tokens_per_entry"),
                "llm.batching.reserve_output_tokens_per_entry",
                defaults.reserve_output_tokens_per_entry,
                1,
            ),
            max_output_tokens_per_entry=_int(
                raw.get("max_output_tokens_per_entry"),
                "llm.batching.max_output_tokens_per_entry",
                defaults.max_output_tokens_per_entry,
                1,
            ),
        )
        if value.max_entry_tokens >= value.max_input_tokens:
            raise ConfigError(
                "llm.batching.max_entry_tokens must be less than llm.batching.max_input_tokens"
            )
        if value.retry_max_seconds < value.retry_base_seconds:
            raise ConfigError(
                "llm.batching.retry_max_seconds must be at least llm.batching.retry_base_seconds"
            )
        if value.response_format not in {"json_object", "prompt_only"}:
            raise ConfigError(
                "llm.batching.response_format must be json_object or prompt_only"
            )
        return value

    def _parse_news_batch(self, raw: dict[str, Any]) -> AINewsBatchConfig:
        d = AINewsBatchConfig()
        value = AINewsBatchConfig(
            enabled=_bool(raw.get("enabled"), "ai_news.batching.enabled", d.enabled),
            source=raw.get("source", d.source),
            summary_agent=raw.get("summary_agent", d.summary_agent),
            max_entries=_int(
                raw.get("max_entries"), "ai_news.batching.max_entries", d.max_entries, 1
            ),
            chunk_size=_int(
                raw.get("chunk_size"), "ai_news.batching.chunk_size", d.chunk_size, 1
            ),
            chunk_max_input_tokens=_int(
                raw.get("chunk_max_input_tokens"),
                "ai_news.batching.chunk_max_input_tokens",
                d.chunk_max_input_tokens,
                1000,
            ),
            max_workers=_int(
                raw.get("max_workers"),
                "ai_news.batching.max_workers",
                d.max_workers,
                1,
                32,
            ),
            reduce_max_input_tokens=_int(
                raw.get("reduce_max_input_tokens"),
                "ai_news.batching.reduce_max_input_tokens",
                d.reduce_max_input_tokens,
                1000,
            ),
            max_output_tokens=_int(
                raw.get("max_output_tokens"),
                "ai_news.batching.max_output_tokens",
                d.max_output_tokens,
                1,
            ),
            deduplicate=_bool(
                raw.get("deduplicate"), "ai_news.batching.deduplicate", d.deduplicate
            ),
            similarity_threshold=_number(
                raw.get("similarity_threshold"),
                "ai_news.batching.similarity_threshold",
                d.similarity_threshold,
                0,
            ),
            publish_partial=_bool(
                raw.get("publish_partial"),
                "ai_news.batching.publish_partial",
                d.publish_partial,
            ),
            missing_summary=raw.get("missing_summary", d.missing_summary),
        )
        if value.source not in {"entry_summaries", "raw_entries", "prefer_summaries"}:
            raise ConfigError("ai_news.batching.source is invalid")
        if not 0 <= value.similarity_threshold <= 1:
            raise ConfigError(
                "ai_news.batching.similarity_threshold must be in range 0..1"
            )
        if value.missing_summary not in {"summarize_inline", "skip"}:
            raise ConfigError("ai_news.batching.missing_summary is invalid")
        return value

    def _parse_output(self, raw: dict[str, Any], d: OutputConfig) -> OutputConfig:
        known = {
            key: raw[key] for key in raw if key in OutputConfig.__dataclass_fields__
        }
        for key in (
            "max_bullets",
            "overview_max_sentences",
            "max_sections",
            "max_items_per_section",
            "max_sources_per_item",
        ):
            if key in known:
                known[key] = _int(known[key], f"output.{key}", getattr(d, key), 0)
        for key in (
            "include_why_it_matters",
            "include_sources",
            "include_overview",
            "include_opinions",
            "include_watchlist",
        ):
            if key in known:
                known[key] = _bool(known[key], f"output.{key}", getattr(d, key))
        return replace(d, **known)

    def _parse_storage(self, raw: dict[str, Any]) -> StorageConfig:
        d = StorageConfig()
        backend = raw.get("backend", d.backend)
        if backend != "sqlite":
            raise ConfigError("storage.backend must be sqlite")
        # Relative fallback keeps test/library imports writable when no config
        # exists at all; deployed config retains the documented /app/data path.
        path = raw.get(
            "path", d.path if self._config_file_exists else "data/miniflux-ai.db"
        )
        if not isinstance(path, str) or not path:
            raise ConfigError("storage.path must be a non-empty path")
        return StorageConfig(
            backend,
            path,
            _int(
                raw.get("summary_retention_days"),
                "storage.summary_retention_days",
                d.summary_retention_days,
                0,
            ),
            _int(
                raw.get("report_retention_count"),
                "storage.report_retention_count",
                d.report_retention_count,
                1,
            ),
            _int(
                raw.get("job_retention_days"),
                "storage.job_retention_days",
                d.job_retention_days,
                0,
            ),
        )

    def _validate_agents(self) -> None:
        for name, agent in self.agents.items():
            if not isinstance(agent, dict):
                raise ConfigError(f"agents.{name} must be a mapping")
            if not agent.get("input"):
                raise ConfigError(
                    f"agents.{name}.input is required but missing or empty"
                )

    def get_agent_batching(self, name: str) -> LLMBatchConfig:
        agent = self.agents[name]
        override = _mapping(agent.get("batch"), f"agents.{name}.batch")
        values = self.llm_batching.__dict__.copy()
        for key, raw in override.items():
            if key not in values:
                raise ConfigError(f"agents.{name}.batch.{key} is unknown")
            values[key] = raw
        # Route overrides through the same validation, preserving global defaults.
        return self._parse_llm_batch(values)

    def get_agent_output(self, name: str) -> OutputConfig | None:
        raw = self.agents[name].get("output")
        return (
            self._parse_output(_mapping(raw, f"agents.{name}.output"), OutputConfig())
            if raw is not None
            else None
        )

    def get_config_value(self, section, key, default=None):
        return _mapping(self.c.get(section), section).get(key, default)
