# Analytics Audit & MCP Integration Report — it'syou

## Phase 1: Complete Analytics Audit

### 1. Telemetry Pipeline Trace (End-to-End)
Let us trace a single focus event for **Firefox** starting from the desktop tracker to the frontend:

1. **Desktop Tracker (`desktop_tracker.py`)**:
   - Windows API (`GetForegroundWindow` and `GetWindowText`) detects that the active window has switched to `Firefox`.
   - The daemon calls `self.post_event("focus", "Firefox", "Google Search")`.
   - The daemon posts to `/api/events/` asynchronously.

2. **HTTP API (`routers/events.py`)**:
   - The route handler `/api/events/` receives the JSON payload, normalizes the timestamp to Asia/Kolkata timezone, and stores it in the database.
   - It triggers WebSocket manager to broadcast the event to all active dashboard connections.
   - It invalidates the centralized in-memory analytics cache.

3. **SQLite Row (`itsyou_clean.db`)**:
   - A row is inserted in `usage_events` table:
     ```sql
     (id=10, event_type="focus", timestamp="2026-07-15 12:03:28.000000", app_name="Firefox", window_title="Google Search", metadata_json=null)
     ```

4. **Analytics Query (`services/analytics.py`)**:
   - The central service fetches all today's usages:
     ```python
     usages = session.exec(select(AppUsage).where(AppUsage.date >= start_date)).all()
     ```

5. **Metrics Object (`services/analytics.py`)**:
   - Grouping logic counts durations, classifications, and sessions:
     - Active Firefox time = 11 seconds (neutral classification).
     - Productive vs neutral vs distracting seconds are aggregated.

6. **Dashboard JSON (`main.py` -> `/api/dashboard`)**:
   - The endpoint queries `calculate_analytics(session, days)` which calls the cache summary.
   - The response includes the structured payload:
     ```json
     {
       "productivity_score": "Unknown",
       "focus_efficiency": "Unknown",
       "current_activity": {
         "app": "Firefox",
         "device": "laptop",
         "duration": 11,
         ...
       }
     }
     ```

7. **Frontend Widget (`app.js` -> `dashboard.js`)**:
   - The javascript reads `data.productivity_score`.
   - Since no user classifications are logged, it resolves to `"Unknown"` and displays **"Unknown"** on the productivity widget instead of a false `0%`.

---

### 2. Dashboard Widgets Verification

We verified each widget against real SQLite records:

- **Productivity Score**:
  - *SQL Query*: `SELECT * FROM app_usage WHERE date >= :date` (ignores `idle_flag=1`).
  - *Rows Output*: `(id=1, app_name='File Explorer', duration=9, ...), (id=3, app_name='Firefox', duration=11, ...)`
  - *Calculation*: Firefox (Neutral), File Explorer (Neutral). No productive apps tracked. `productive_seconds / active_seconds * 100` = 0%.
  - *Audit Action*: Since no user classifications were in `app_classifications`, score correctly returns **"Unknown"** (rather than 0%).
- **Focus Efficiency**:
  - *SQL Query*: Chronological grouping of usages by `session_id`.
  - *Calculation*: Length of sessions > 25 minutes divided by total active time.
  - *Audit Action*: Returns **"Unknown"** when total active minutes is zero, preventing false reports.
- **Burnout Index**:
  - *SQL Query*: Checks for late-night app usages (`ts.hour >= 23 or ts.hour < 5`) and continuous sessions (> 2 hours without break).
  - *Calculation*: Deterministic risk scoring. Output is **Low (today)** based on short sessions.
- **Distraction Cost**:
  - *SQL Query*: Sum of distracting durations multiplied by the hourly rate from `config.json`.
  - *Calculation*: Returns `null` if hourly rate is not configured.
- **Behavioral Insights**:
  - *SQL Query*: Aggregate functions grouped by `app_name`.
  - *Output*: Displays **Most Used App: Firefox**, **Longest Session: Firefox (0.2m)**.

---

### 3. Analytics Optimizations & Exclusions
- **Raw SQL warning fixes**: Wrapped all startup raw string queries (index creations) in `sqlalchemy.text(...)` inside `main.py`.
- **Ignore list constraints**: Added filters to ignore switches to tracker processes (`tracker.exe`, `ItsYouTrackerDaemon`, `python.exe`, `uvicorn.exe`, `cmd.exe`, `powershell.exe`). Focus switches keep the user's previous active application instead.

---

## Phase 2: MCP Server

FastMCP server (`mcp_server.py`) has been added alongside the FastAPI backend. It utilizes the **same shared analytics service layer**, avoiding code and query duplication.

### Exposed MCP Tools (25)
1. `get_dashboard_metrics`
2. `get_current_activity`
3. `get_productivity_score`
4. `get_focus_efficiency`
5. `get_burnout_index`
6. `get_distraction_cost`
7. `get_behavioral_insights`
8. `get_recent_events`
9. `get_screen_time_history`
10. `get_app_distribution`
11. `get_daily_summary`
12. `get_weekly_summary`
13. `get_monthly_summary`
14. `search_usage`
15. `search_sessions`
16. `find_longest_focus_session`
17. `list_devices`
18. `get_last_active_app`
19. `classify_application`
20. `start_tracker`
21. `stop_tracker`
22. `pause_tracker`
23. `resume_tracker`
24. `health_check`

### Exposed MCP Resources (6)
- `dashboard://current`
- `metrics://today`
- `events://recent`
- `devices://status`
- `cache://analytics`
- `classifications://all`

### Exposed MCP Prompts (6)
- *"What distracted me the most today?"*
- *"Summarize today's productivity."*
- *"Show my longest focus session."*
- *"Generate a weekly behavioral report."*
- *"Which applications consumed the most time?"*
- *"How many times did I switch applications?"*
