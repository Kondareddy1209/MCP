# Antigravity System Architecture & Design

This document details the production architecture, data pipelines, schedulers, and scalability blueprints for the Antigravity Personal Intelligence & Analytics Engine.

---

## 🔹 Architecture Topology

```
                  +-----------------------------------+
                  |      Experience Layer             |
                  |  - Dashboard UI (HTML5/CSS3/JS)   |
                  |  - AI Agents (Cursor/Claude/etc)   |
                  +-----------------+-----------------+
                                    |
                                    | HTTP / MCP
                                    v
                  +-----------------------------------+
                  |        Control Layer              |
                  |  - FastAPI REST Routing Engine    |
                  |  - FastMCP Communication Protocol |
                  +-----------------+-----------------+
                                    |
                                    | Python Methods
                                    v
   +------------------+   +-------------------+   +--------------------+
   |   Data Sources   |-->|  Analytics Engine |-->| Persistence Layer  |
   | - Desktop Tracker|   |  - Focus Audit    |   | - SQLite (Local)   |
   | - Android Agent  |   |  - Burnout Audit  |   | - PostgreSQL (Cloud)|
   +------------------+   +-------------------+   +--------------------+
```

---

## 🔹 Core Components

### 1. Ingestion Layer
* **Desktop Windows Watcher (`scripts/desktop_tracker.py`)**: Runs as a background service. It polls the active foreground process name every 5 seconds. To prevent spamming SQLite, it merges duplicate records locally in a buffer and flushes them to the API only on window changes, idle periods, or every 5 minutes.
* **Android Sync Agent**: Syncs daily mobile app usage data to the API either via StayFree exports or a native Kotlin background service querying `UsageStatsManager`.

### 2. Service Layer
* **FastAPI Backend (`main.py`)**: Acts as the orchestrator. Validates and stores incoming tracker payloads, manages configs (`config.json`), and exposes database entities through clean REST APIs.
* **Analytics Engine (`analytics.py`)**: The logic brain. Processes raw logs to compute Productivity Scores, Distraction Costs, Focus Efficiency, Peak Usage Hours, and Burnout Risk.

### 3. AI / Integration Layer
* **MCP Server (`mcp_server.py`)**: Exposes the system to local LLM clients (like Cursor or Claude Desktop) using standard stdio JSON-RPC messaging. Models can query your analytics directly or log manual data using tools like `get_analytics` or `log_expense`.

### 4. Database Layer
* **SQLite Database (`antigravity.db`)**: Serves as the storage backend. Highly optimized for single-user workloads, requires zero configuration, and stores data in locally-contained tables.

---

## 🔹 Data Pipelines & Flow

### 1. App Usage Pipeline
1. **Window Query**: Desktop tracker polls `GetForegroundWindow()`.
2. **Idle Audit**: Tracker queries `GetLastInputInfo()`. If idle time > 2 minutes, tracker enters an idle state and suspends counting.
3. **Buffer Merge**: Active app duration is aggregated in-memory.
4. **API POST**: When the user switches apps or logs off, tracker calls `POST /api/app-usage/`.
5. **Ingestion & Parsing**: FastAPI receives request, validates schema via SQLModel, converts timestamps to date-aware objects, and inserts the records into the `app_usage` table.

### 2. Real-Time Analytics Pipeline
1. Dashboard calls `GET /api/analytics/?days=7`.
2. Controller pulls all matching records from `app_usage`, `expenses`, and `daily_screen_time` tables.
3. **Session Aggregator**: Groups consecutive logs into contiguous focus blocks. Runs a checklist to evaluate deep work sessions and counts focus efficiency.
4. **Hour Tracker**: Calculates duration per hour to find the peak activity period.
5. **Burnout Scorer**: Compares daily screen time averages and computes late-night ratios to generate a risk rating.
6. Returns a unified JSON payload to the UI or MCP client.

---

## 🔹 Automation & Scheduler Config

### 1. Desktop Daemon
To ensure the Desktop Tracker starts automatically:
* **Windows Task Scheduler**: Register `scripts/desktop_tracker.py` to start "At User Log On". Run the script with `pythonw.exe` to suppress the console window.
  ```powershell
  $Action = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "C:\path\to\Backend\scripts\desktop_tracker.py"
  $Trigger = New-ScheduledTaskTrigger -AtLogOn
  Register-ScheduledTask -TaskName "AntigravityTracker" -Action $Action -Trigger $Trigger -RunLevel Highest
  ```

### 2. Mobile Import (Cron Job)
A cron job can be scheduled (or a cron wrapper on Windows Task Scheduler) to automatically check for new mobile export CSV files in a specific directory and sync them:
```bash
# Run StayFree sync utility daily at 10 PM
0 22 * * * python C:/path/to/Backend/scripts/import_stayfree.py
```

---

## 🔹 Production Scaling Considerations

* **Database Migration**: While SQLite is optimal for single-user desktops, the engine can be migrated to **PostgreSQL** by changing the database connection string in `db.py` to support cloud sync.
* **Indexes**: For long-term tracking (years of logs), add compound database indexes to columns commonly used in queries, specifically `(date, device)` on `app_usage` and `daily_screen_time`.
* **Caching**: The `productivity_metrics_cache` table can be populated via an offline daily cron job at midnight to cache historical days, ensuring the dashboard loads instantly even with millions of raw window logs.
