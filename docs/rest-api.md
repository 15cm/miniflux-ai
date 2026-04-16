# REST API

The Flask server starts automatically when `webhook_secret` or `ai_news_schedule` is configured.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/miniflux-ai` | HMAC signature | Miniflux webhook receiver |
| `POST` | `/api/reprocess` | Bearer token | Force reprocess entries (see below) |
| `GET`  | `/rss/ai-news` | None | AI news RSS feed |

## `POST /api/reprocess`

Triggers immediate reprocessing of entries through all configured agents.

**Auth**: If `webhook_secret` is set in config, include header `Authorization: Bearer <webhook_secret>`.

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
curl -X POST http://localhost/api/reprocess \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your_secret' \
  -d '{"scope": "unread"}'

# Reprocess last 50 entries
curl -X POST http://localhost/api/reprocess \
  -H 'Content-Type: application/json' \
  -d '{"scope": "last_n", "n": 50}'

# Reprocess entries from the last 6 hours
curl -X POST http://localhost/api/reprocess \
  -H 'Content-Type: application/json' \
  -d '{"scope": "duration", "duration": "6h"}'
```

**Response**:
```json
{"status": "ok", "queued": 42}
```

Processing runs in background; response returns immediately with count of queued entries.
