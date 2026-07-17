# REST API

The Flask server starts automatically when `webhook_secret` or `ai_news_schedule` is configured.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/miniflux-ai` | HMAC signature | Miniflux webhook receiver |
| `POST` | `/api/reprocess` | Optional bearer token | Force reprocess entries (see below) |
| `POST` | `/api/generate-daily-news` | Optional bearer token | Trigger daily news generation immediately |
| `GET` | `/api/jobs/<job_id>` | Optional bearer token | Get durable background-job status |
| `GET`  | `/rss/ai-news` | None | AI news RSS feed |

## `POST /api/reprocess`

Triggers immediate reprocessing of entries through all configured agents.

**Auth**: None required.

**Request body** (JSON):

| `scope` | Extra fields | Description |
|---------|-------------|-------------|
| `"unread"` | — | All current unread entries |
| `"all"` | — | All entries (up to 10000) |
| `"last_n"` | `"n": <int>` | Most recent N entries |
| `"duration"` | `"duration": "<N><unit>"` | Entries published within last duration. Units: `m` (minutes), `h` (hours), `d` (days) |

**Examples**:

```bash
# Reprocess all unread entries
curl -X POST http://localhost:80/api/reprocess \
  -H 'Content-Type: application/json' \
  -d '{"scope": "unread"}'

# Reprocess last 50 entries
curl -X POST http://localhost:80/api/reprocess \
  -H 'Content-Type: application/json' \
  -d '{"scope": "last_n", "n": 50}'

# Reprocess entries from the last 6 hours
curl -X POST http://localhost:80/api/reprocess \
  -H 'Content-Type: application/json' \
  -d '{"scope": "duration", "duration": "6h"}'
```

**Response**:
```json
{"status": "queued", "job_id": "uuid", "queued": 42}
```

Processing runs in background; response returns immediately with count of queued entries.

## `POST /api/generate-daily-news`

Triggers daily news generation. Optionally fetches entries by scope and writes them to `entries.json` before generating (no agents are run).

**Auth**: None required.

**Request body** (JSON, optional):

| `scope` | Extra fields | Description |
|---------|-------------|-------------|
| _(omitted)_ | — | Generate from existing `entries.json` immediately |
| `"unread"` | — | Fetch all unread entries, then generate |
| `"all"` | — | Fetch all entries (up to 10000), then generate |
| `"last_n"` | `"n": <int>` | Fetch most recent N entries, then generate |
| `"duration"` | `"duration": "<N><unit>"` | Fetch entries published within last duration, then generate. Units: `m`, `h`, `d` |

**Examples**:

```bash
# Generate from existing entries.json
curl -X POST http://localhost:80/api/generate-daily-news

# Fetch last 6 hours of entries, then generate
curl -X POST http://localhost:80/api/generate-daily-news \
  -H 'Content-Type: application/json' \
  -d '{"scope": "duration", "duration": "6h"}'
```

**Response** (no scope):
```json
{"status": "queued", "job_id": "uuid", "queued": 0}
```

**Response** (with scope):
```json
{"status": "queued", "job_id": "uuid", "queued": 42}
```

Generation runs in background; response returns immediately. Batch mode persists reports in SQLite, so RSS reads never clear a report. Query the job endpoint for `queued`, `running`, `completed`, `partial`, or `failed` status. Enable bearer protection with `api.bearer_token`, `api.protect_manual_endpoints`, and `api.protect_job_endpoint`.
