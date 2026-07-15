# Antigravity Behavioral Intelligence Platform — Integration & Setup Guide

This guide documents the full system setup, data flow, integrations, and production hardening blueprints for the upgraded Antigravity Platform.

---

## 🏗️ System Architecture & Data Flow

```
+------------------+                   +----------------------------------+
|                  |   Raw Events      |                                  |
| Windows Tracker  |------------------>|         FastAPI Backend          |
| (100ms Polling)  |   (REST API)      |   (main.py / routers/events.py)  |
|                  |                   |                                  |
+------------------+                   +----------------+-----------------+
        |                                               |
        | Aggregated Usage                              | Store Event
        | (1 min buffers)                               v
        |                              +----------------------------------+
        v                              |                                  |
+------------------+                   |          SQLite Database         |
|                  |   REST API POST   |          (antigravity.db)        |
|  AppUsage Blocks |------------------>|                                  |
|                  |                   +----------------+-----------------+
+------------------+                                    |
                                                        | Fetch Data
                                                        v
+------------------+                   +----------------------------------+
|                  |   REST API GET    |                                  |
|   Dashboard UI   |------------------>|         Analytics Engine         |
| (HTML/CSS/JS)    |                   |   (Focus, Burnout, Habits math)  |
|                  |                   |                                  |
+------------------+                   +----------------+-----------------+
                                                        |
                                                        | JSON Response
                                                        v
+------------------+                   +----------------------------------+
|                  |   Stdio Protocol  |                                  |
|    AI Client     |<=================>|            MCP Server            |
| (Cursor/Claude)  |   (mcp_server.py) |   (get_daily_summary, etc.)      |
|                  |                   |                                  |
+------------------+                   +----------------------------------+
```

### 1. Ingestion Flow
1. The **Desktop Tracker** runs a background polling thread (100ms resolution) that checks active window state and counts keyboard/mouse events.
2. Every 60 seconds (or on window switch), the tracker computes the `activity_score` (events/minute) and sends an `INPUT_ACTIVITY` or `APP_SWITCH` raw event to `/api/events/`.
3. Simultaneously, the tracker posts an aggregated usage interval block to `/api/app-usage/` with UUID-based `session_id`, `input_events`, and `idle_flag` set according to an adaptive threshold (rolling average of activity * 0.5).

### 2. Analytics Execution
- The **Analytics Engine** (`analytics.py`) groups logs into Focus Sessions. If a session is $\ge 25$ minutes, productive, and has no distraction or idle gaps, it is classified as **Deep Work**.
- Advanced productivity and behavioral burnout scores are calculated dynamically using deep work ratios, late-night usage percentages, and overwork days.

---

## 🔌 MCP AI Agent Tools Schema

The MCP server exposes rich behavioral parameters to AI models. Below are tool specs:

### 1. `get_daily_summary`
- **Purpose**: Provides high-level coaching feedback.
- **Example Response**:
  ```json
  {
    "productivity_score": "76.4%",
    "focus_efficiency": "33.3%",
    "burnout_score": "45.2/100 (Medium Risk)",
    "total_expenses_today": "INR 320.0",
    "biggest_time_waster": "YouTube (1.2 hrs)",
    "habit_insights": "Peak productivity hour: 10:00 | Habits: VS Code, Chrome",
    "suggestion": "Your peak productivity is at 10 AM. Guard this hour from distractions to maximize focus."
  }
  ```

### 2. `get_burnout_score`
- **Purpose**: Checks exhaustion risks.
- **Example request**: `{ "days": 7 }`
- **Example Response**: `"Burnout Index: 45.2/100 | Risk Category: Medium"`

---

## ⚡ Setup & Run Instructions

### Step 1: Install Dependencies
```bash
pip install fastapi uvicorn sqlmodel pandas python-dateutil mcp httpx pytest requests
```

### Step 2: Seed the Mock Data
Populate the database with historical logs for testing:
```bash
python scripts/seed_data.py
```

### Step 3: Run the FastAPI Server & Dashboard
```bash
uvicorn main:app --reload --port 8000
```
Open `http://localhost:8000/` to inspect the live dashboard.

### Step 4: Run the Window & Input Tracker Daemon
```bash
python scripts/desktop_tracker.py
```

### Step 5: Start the Intervention Engine Alerting Daemon
```bash
python intervention_engine.py
```

---

## 🔒 Production Hardening Blueprints

### 1. Database Migration to PostgreSQL
Change the connection engine in `db.py`:
```python
DATABASE_URL = "postgresql://user:password@localhost:5432/antigravity"
```
Install Alembic for schema migrations:
```bash
alembic init alembic
```

### 2. Run Tracker as a Background Windows Service
Configure the Task Scheduler to launch `scripts/desktop_tracker.py` using `pythonw.exe` on startup. This detaches it from the terminal and runs it silently. Add a watchdog retry loop to recover from API connection crashes automatically.

### 3. API Security & Rate Limiting
- **Token-based Auth**: Add OAuth2/JWT middleware to FastAPI routers to secure endpoints from external local network exposure.
- **Rate Limiting**: Protect endpoints from ingestion spam using `slowapi` or standard Redis rate limiters.
