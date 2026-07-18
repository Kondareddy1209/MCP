# it'syou — Project Status

> Last updated: 2026-07-18

---

## What's Done ✅

### Core Pipeline
- Desktop tracker (Windows, PyWinHook) → `POST /api/events/` → SQLite WAL
- Session tracking with merge/jitter/idle-filtering (`services/session_engine.py`)
- Behavior engine: productivity score (null-vs-estimated), focus, burnout, distraction cost (`services/behavior_engine.py`)
- Analytics orchestration with in-memory cache and cache invalidation (`services/analytics.py`)
- WebSocket real-time push (`/ws/live`) broadcasting on every event insert
- Multi-device ingestion via `POST /api/ingest`

### API
- `/api/dashboard` — full dashboard aggregate (all metrics, events, screen time)
- `/api/analytics/` — raw analytics
- `/api/analytics/daily-summary` — condensed daily view (C4 fixed)
- `/api/events/` — event ingestion + WebSocket broadcast
- `/api/app-usage/`, `/api/app-usage/bulk` — app usage ingestion
- `/api/explain?question=...&days=N` — conversational behavioral analysis (new V3 feature)
- `/api/tracker/status|pause|resume|start|stop` — tracker daemon control
- `/api/alerts` — intervention log reader

### MCP Server (26 tools, 6 resources, 6 prompts)
- All 25 original tools + `explain_productivity_change()` (V3 conversational tool)
- `compare_last_week()` now genuinely isolates prior 7-day window (M6 fixed)
- Productivity tools surface `estimated_score` alongside `score`

### Frontend Dashboard
- WebSocket primary real-time updates; 60s resilience fallback poll
- Pulse badge uses same regex ruleset as backend `classification.py`
- Estimated score renders as `~N% (estimated)` with tooltip when no user classifications
- Recommendation display corrected to `recommendations[0]`

### Intervention Engine
- All three critical bugs fixed (C1: wrong key paths, C2: missing import, C3: duplicated burnout logic)
- Delegates burnout math to `BehaviorEngine.analyze_burnout()` — single source of truth
- Auto-starts as daemon thread via `main.py` lifespan handler when `config.json` has `"run_intervention_engine": true`
- Disabled by default (set flag to `true` to enable)

### Tests
- `tests/test_api.py`: 13 original tests — all passing
- `tests/test_extended.py`: 24 new tests — all passing (37 total)
  - Session engine: merge, jitter, M3 tz-aware regression, empty list
  - Behavior engine: empty sessions, all-idle, single point, M7 double regression lock
  - API: C4 daily-summary, explain endpoint, cache invalidation, dashboard estimated_score
  - Comparisons: M6 window isolation, explain required-key structure
  - Regressions: payload schema validation, active app ignore-list filter, dynamic screen-time fallback aggregation, currently active metadata row, window titles context auto-classification, Today's hourly screen-time buckets

---

## Known Limitations ⚠️

| # | Limitation | Impact |
|---|------------|--------|
| L1 | `compare_last_week()` MCP tool isolates prior 7d window correctly, but the REST `explain` endpoint's "prior" period uses a 2x rolling window approximation rather than a hard-cut offset query. Exact week-over-week requires `days=7`. | Low — clearly documented in API response `note` field |
| L2 | `auto_classify()` uses regex heuristics that default to `neutral` for unknown apps. Unfamiliar apps will have `estimate_confidence: "auto-classified"` but may be miscategorized until user adds them to `app_classifications`. | Expected — by design |
| L3 | WebSocket reconnect uses a 3s fixed backoff with no maximum; a crashed server will cause infinite reconnect spam. | Low — local development context |
| L4 | `generate_ai_dashboard` simulates data when DB has < threshold records. Simulation is labeled `"status": "SIMULATED"`. | Expected — labeled in response |

---

## How to Run Locally

### Start the API server
```powershell
cd "C:\Users\Konda Reddy\OneDrive\Desktop\Backend"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Dashboard: http://localhost:8000  
API docs: http://localhost:8000/docs

### Enable the intervention engine
```json
// config.json
{
  "hourly_rate": 200,
  "currency": "INR",
  "run_intervention_engine": true
}
```
Restart the server after changing this flag. The engine runs as a daemon thread — no separate process needed.

### Run the test suite
```powershell
python -m pytest tests/ -v
```
Expected: **34 passed**

### Use the conversational endpoint
```
GET http://localhost:8000/api/explain?question=Why+was+my+productivity+lower+today&days=1
```

### Use the MCP server (AI agent access)
```powershell
python mcp_server.py
```
Exposes 26 tools including `explain_productivity_change(question, days)`.

---

## Architecture

```
[Windows Desktop Tracker]
       │  POST /api/events/ + /api/app-usage/
       ▼
[FastAPI Backend (main.py)]
       │
       ├── SQLite WAL (itsyou_clean.db)
       │
       ├── [Session Engine] ← reconstructs focus sessions from raw logs
       │
       ├── [Behavior Engine] ← computes all metrics (no DB access)
       │
       ├── [Analytics Service] ← cache layer + orchestration
       │       ├── REST API (/api/dashboard, /api/explain, ...)
       │       ├── WebSocket (/ws/live) — push on every event
       │       └── MCP Server (mcp_server.py) — 26 tools
       │
       └── [Intervention Engine] ← daemon thread, fires behavioral alerts
```
