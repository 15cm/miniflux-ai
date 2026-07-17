"""Small durable SQLite store. Each operation owns its connection."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EntrySummary:
    entry_id: int
    agent_name: str
    source_hash: str
    title: str
    url: str
    category: str
    published_at: str
    summary_markdown: str
    structured_json: str | None
    model: str
    prompt_hash: str


@dataclass(frozen=True)
class DailyReport:
    id: str
    job_id: str
    title: str
    content_markdown: str
    source_entry_ids: list[str]
    model: str
    created_at: str = ""


class SummaryStore:
    def __init__(self, path: str):
        self.path = path

    def _connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA busy_timeout = 5000")
        return con

    def initialize(self) -> None:
        with self._connect() as con:
            con.execute("PRAGMA journal_mode = WAL")
            con.executescript(
                """
            CREATE TABLE IF NOT EXISTS entry_summaries (
              entry_id INTEGER NOT NULL, agent_name TEXT NOT NULL, source_hash TEXT NOT NULL,
              title TEXT NOT NULL, url TEXT NOT NULL, category TEXT NOT NULL, published_at TEXT NOT NULL,
              summary_markdown TEXT NOT NULL, structured_json TEXT, model TEXT NOT NULL,
              prompt_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY (entry_id, agent_name));
            CREATE INDEX IF NOT EXISTS idx_entry_summaries_published ON entry_summaries(published_at DESC);
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
              requested_count INTEGER NOT NULL DEFAULT 0, processed_count INTEGER NOT NULL DEFAULT 0,
              failed_count INTEGER NOT NULL DEFAULT 0, error TEXT, metadata_json TEXT,
              created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT);
            CREATE TABLE IF NOT EXISTS daily_reports (
              id TEXT PRIMARY KEY, job_id TEXT NOT NULL, title TEXT NOT NULL,
              content_markdown TEXT NOT NULL, source_entry_ids_json TEXT NOT NULL,
              model TEXT NOT NULL, created_at TEXT NOT NULL,
              FOREIGN KEY(job_id) REFERENCES jobs(id));
            """
            )

    def get_current_summary(
        self, entry_id, agent_name, source_hash, prompt_hash, model
    ):
        self.initialize()
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM entry_summaries WHERE entry_id=? AND agent_name=? AND source_hash=? AND prompt_hash=? AND model=?",
                (entry_id, agent_name, source_hash, prompt_hash, model),
            ).fetchone()
        return dict(row) if row else None

    def upsert_summary(self, summary: EntrySummary) -> None:
        self.initialize()
        now = _now()
        with self._connect() as con:
            con.execute(
                """INSERT INTO entry_summaries(entry_id,agent_name,source_hash,title,url,category,published_at,summary_markdown,structured_json,model,prompt_hash,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(entry_id,agent_name) DO UPDATE SET source_hash=excluded.source_hash,title=excluded.title,url=excluded.url,category=excluded.category,published_at=excluded.published_at,summary_markdown=excluded.summary_markdown,structured_json=excluded.structured_json,model=excluded.model,prompt_hash=excluded.prompt_hash,updated_at=excluded.updated_at""",
                (
                    summary.entry_id,
                    summary.agent_name,
                    summary.source_hash,
                    summary.title,
                    summary.url,
                    summary.category,
                    summary.published_at,
                    summary.summary_markdown,
                    summary.structured_json,
                    summary.model,
                    summary.prompt_hash,
                    now,
                    now,
                ),
            )

    def list_summaries(
        self, *, entry_ids=None, limit=None, after=None, agent_name=None
    ):
        self.initialize()
        query, values = "SELECT * FROM entry_summaries", []
        clauses = []
        if entry_ids is not None:
            ids = list(entry_ids)
            if not ids:
                return []
            clauses.append("entry_id IN (" + ",".join("?" for _ in ids) + ")")
            values.extend(ids)
        if after is not None:
            clauses.append("published_at >= ?")
            values.append(after)
        if agent_name is not None:
            clauses.append("agent_name = ?")
            values.append(agent_name)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY published_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            values.append(limit)
        with self._connect() as con:
            return [dict(row) for row in con.execute(query, values).fetchall()]

    def create_job(self, kind, requested_count=0, metadata=None) -> str:
        self.initialize()
        job_id = str(uuid4())
        with self._connect() as con:
            con.execute(
                "INSERT INTO jobs(id,kind,status,requested_count,metadata_json,created_at) VALUES(?,?,?,?,?,?)",
                (
                    job_id,
                    kind,
                    "queued",
                    requested_count,
                    json.dumps(metadata or {}),
                    _now(),
                ),
            )
        return job_id

    def update_job(self, job_id, **fields) -> None:
        allowed = {
            "status",
            "processed_count",
            "failed_count",
            "error",
            "metadata_json",
            "started_at",
            "completed_at",
        }
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"unsupported job fields: {invalid}")
        if "status" in fields and fields["status"] not in {
            "queued",
            "running",
            "completed",
            "partial",
            "failed",
        }:
            raise ValueError("invalid job status")
        if fields.get("status") == "running":
            fields.setdefault("started_at", _now())
        if fields.get("status") in {"completed", "partial", "failed"}:
            fields.setdefault("completed_at", _now())
        if not fields:
            return
        sql = ", ".join(f"{key}=?" for key in fields)
        with self._connect() as con:
            con.execute(f"UPDATE jobs SET {sql} WHERE id=?", [*fields.values(), job_id])

    def get_job(self, job_id):
        self.initialize()
        with self._connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def save_daily_report(self, report: DailyReport) -> None:
        self.initialize()
        with self._connect() as con:
            con.execute(
                "INSERT INTO daily_reports(id,job_id,title,content_markdown,source_entry_ids_json,model,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    report.id,
                    report.job_id,
                    report.title,
                    report.content_markdown,
                    json.dumps(report.source_entry_ids),
                    report.model,
                    report.created_at or _now(),
                ),
            )

    def latest_daily_reports(self, limit: int):
        self.initialize()
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM daily_reports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        result = [dict(row) for row in rows]
        for row in result:
            row["source_entry_ids"] = json.loads(row.pop("source_entry_ids_json"))
        return result

    def cleanup(
        self,
        *,
        summary_retention_days: int,
        report_retention_count: int,
        job_retention_days: int,
    ) -> None:
        # Retention explicitly callable; scheduling is deployment policy.
        with self._connect() as con:
            con.execute(
                "DELETE FROM entry_summaries WHERE updated_at < datetime('now', ?)",
                (f"-{summary_retention_days} days",),
            )
            con.execute(
                "DELETE FROM jobs WHERE created_at < datetime('now', ?)",
                (f"-{job_retention_days} days",),
            )
            con.execute(
                "DELETE FROM daily_reports WHERE id NOT IN (SELECT id FROM daily_reports ORDER BY created_at DESC LIMIT ?)",
                (report_retention_count,),
            )
