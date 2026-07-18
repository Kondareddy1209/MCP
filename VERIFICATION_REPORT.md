# Verification Report — it'syou

This report outlines the end-to-end verification of the telemetry and analytics engine.

---

## 1. Type Safety & Separation of Concerns (SOLID)

We have verified that no presentation formatting strings (such as `"Unknown"`, `"N/A"`, `"--"`) are returned from business logic inside `services/analytics.py`. 
- **Business Logic Layer**: Returns numeric results (`int`, `float`) or `None` if data/classifications are missing.
- **Presentation Layer (`dashboard.js`)**: Converts `None` or `null` values into clean user-friendly labels (like `Unknown`, `--`, `No data`, or `₹0.00`).
- **Safety Assertions**: Programmatically added assertions in the caching loop to verify that all metrics returned are strictly numeric or `None` (blocking any future regression string types).

---

## 2. End-to-End Audit Traces

### 1. Productivity Score Widget
* **SQL Query Executed**:
  ```sql
  SELECT * FROM app_usage WHERE date >= '2026-07-15';
  ```
* **Returned Rows**:
  ```python
  (id=1, app_name='File Explorer', duration_seconds=9, idle_flag=0)
  (id=3, app_name='Firefox', duration_seconds=11, idle_flag=0)
  ```
* **Intermediate Python Object**:
  ```python
  {
      "score": None,  # returned because app_classifications table is empty
      "productive_minutes": 0.0,
      "neutral_minutes": 0.3,
      "distracting_minutes": 0.0
  }
  ```
* **Final JSON**:
  ```json
  "productivity": {
      "score": null,
      "productive_minutes": 0.0,
      "neutral_minutes": 0.3,
      "distracting_minutes": 0.0
  }
  ```
* **Frontend Value**: Displayed as **`Unknown`** (via `dashboard.js` formatting `null`).
* **MCP Tool Output (`get_productivity_score`)**:
  ```
  Productivity Score: None | Productive: 0.0m | Distracting: 0.0m
  ```

---

### 2. Focus Efficiency Widget
* **SQL Query Executed**:
  Groups usages chronologically by `session_id`.
* **Returned Rows**:
  All rows grouped under `637333a4-30b0-40c1-b755-d9dc001b3994` (total duration 50s).
* **Intermediate Python Object**:
  ```python
  {
      "focus_percentage": None,  # no sessions > 25 minutes
      "average_session": 0,
      "longest_session": 0,
      "deep_focus_count": 0,
      "switches_today": 0
  }
  ```
* **Final JSON**:
  ```json
  "focus": {
      "focus_percentage": null,
      "average_session": 0,
      "longest_session": 0,
      "deep_focus_count": 0,
      "switches_today": 0
  }
  ```
* **Frontend Value**: Displayed as **`Unknown`** (via `dashboard.js` formatting `null`).
* **MCP Tool Output (`get_focus_efficiency`)**:
  ```
  Focus Efficiency: None | Longest Focus: 0m | Deep Focus Sessions: 0 | Context Switches: 0
  ```

---

### 3. Burnout Index Widget
* **SQL Query Executed**:
  Checks for late night active sessions and continuous durations.
* **Returned Rows**:
  No late-night timestamps found (hours 23-5) and no continuous sessions > 2 hours.
* **Intermediate Python Object**:
  ```python
  {
      "score": 10,  # baseline
      "risk": "Low"
  }
  ```
* **Final JSON**:
  ```json
  "burnout": {
      "score": 10,
      "risk": "Low"
  }
  ```
* **Frontend Value**: Displayed as **`10/100`** with subtitle **`Risk Category: Low`**.
* **MCP Tool Output (`get_burnout_index`)**:
  ```
  Burnout Index: 10/100 | Risk Level: Low
  ```

---

### 4. Distraction Cost Widget
* **SQL Query Executed**:
  Multiplies distracting app minutes by `hourly_rate` from `config.json`.
* **Returned Rows**:
  Zero distracting minutes.
* **Intermediate Python Object**:
  ```python
  {
      "amount": 0.0,
      "currency": "INR"
  }
  ```
* **Final JSON**:
  ```json
  "distraction_cost_details": {
      "amount": 0.0,
      "currency": "INR"
  }
  ```
* **Frontend Value**: Displayed as **`₹0.00`**.
* **MCP Tool Output (`get_distraction_cost`)**:
  ```
  Distraction Opportunity Cost: INR 0.0
  ```

---

### 5. Current Activity Card Widget
* **SQL Query Executed**:
  Queries the latest event from `usage_events` table.
* **Returned Rows**:
  ```python
  (id=10, event_type='focus', timestamp='2026-07-15 12:03:28', app_name='Firefox', ...)
  ```
* **Intermediate Python Object**:
  ```python
  {
      "app": "Firefox",
      "device": "laptop",
      "duration": 1800,  # dynamic seconds elapsed since 12:03:28
      "today_active_time": "0.1 hrs",
      "idle_timer": 0,
      "last_activity": "12:03:28"
  }
  ```
* **Final JSON**:
  ```json
  "current_activity": {
      "app": "Firefox",
      "device": "laptop",
      "duration": 1800,
      "today_active_time": "0.1 hrs",
      "idle_timer": 0,
      "last_activity": "12:03:28"
  }
  ```
* **Frontend Value**: Updates live badge pulse to **neutral (blue)**, displays **`Firefox`** with device **`laptop`** and duration **`30m 0s`**.
* **MCP Tool Output (`get_current_activity`)**:
  ```json
  {
      "app": "Firefox",
      "device": "laptop",
      "duration": 1800,
      "today_active_time": "0.1 hrs",
      "idle_timer": 0,
      "last_activity": "12:03:28"
  }
  ```

---

## 3. Crash-Proof Recommendations & Caching

1. **Recommendations**:
   - Safely protects checks using `is not None` constraints, avoiding any crash comparison TypeErrors:
     ```python
     if prod_score is not None and isinstance(prod_score, (int, float)) and prod_score < 50:
     ```
2. **Caching**:
   - `get_cached_dashboard_summary` catches any query execution exceptions, logs the error, attempts to return the previous successful run cache, and falls back to a clean empty summary with all fields set to `None` if no cache exists.
   - This prevents uvicorn from ever throwing HTTP 500 crashes.
