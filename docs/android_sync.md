# Android Data Sync Architecture — Antigravity

This document outlines options for capturing real application usage and screen time statistics from Android devices and synchronizing them with the Antigravity backend API.

---

## 🔹 Integration Options

### 1. Manual Entry (Simplest Approach)
* **How it works**: Users view their screen time in settings (under "Digital Wellbeing & parental controls") and manually log the daily total or individual top apps using the Antigravity Dashboard's management console.
* **Pros**: No technical overhead, zero battery impact, works out-of-the-box.
* **Cons**: High friction, lacks granularity.

### 2. Export via Third-Party Apps (Recommended for local setup)
* **How it works**: Use popular screen time applications like **StayFree** which support exporting app usage data as CSV. A Python CLI utility is provided at `scripts/sync_mobile.py` to read StayFree CSV exports, normalize values, prevent duplicates, and ingest them to the backend API.
* **StayFree Export Format**: CSV containing columns `Package Name`, `App Name`, `Date`, `Duration`.
* **Synchronization CLI Script**: Run the sync utility from your command line:
  ```powershell
  # Test parsing and mapping without committing to the database:
  python scripts/sync_mobile.py path/to/stayfree_export.csv --dry-run

  # Run full synchronization to the database:
  python scripts/sync_mobile.py path/to/stayfree_export.csv
  ```
* **Key Features**:
  - **Auto-deduplication**: Checks the database on start and skips rows that have already been imported to prevent double counting.
  - **App Normalization**: Automatically maps common Android package IDs (e.g. `com.android.chrome`) to clean display names (e.g. `Chrome`) so that desktop and mobile usage statistics merge seamlessly.
  - **Robust Parsing**: Supports flexible CSV date parsing formats and parses durations in both seconds and formatted time (`HH:MM:SS`) columns.

### 3. Native Android Application (Advanced Production Route)
* **How it works**: Write a minimal background service on Android using Kotlin/Java that queries the OS's native `UsageStatsManager` API and periodically pushes data to the local server endpoint.
* **API Details**: `UsageStatsManager` provides access to device usage history. Requires the `android.permission.PACKAGE_USAGE_STATS` permission (which the user must manually enable in Settings > Special App Access).
* **Core Kotlin Implementation**:
  ```kotlin
  val usageStatsManager = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
  val endTime = System.currentTimeMillis()
  val startTime = endTime - 24 * 60 * 60 * 1000 // Last 24 hours

  val stats = usageStatsManager.queryAndAggregateUsageStats(startTime, endTime)
  val appUsageList = mutableListOf<AppUsagePayload>()

  for ((packageName, usageStats) in stats) {
      val totalTimeInForeground = usageStats.totalTimeInForeground / 1000 // Convert ms to seconds
      if (totalTimeInForeground > 0) {
          appUsageList.add(
              AppUsagePayload(
                  app_name = getAppNameFromPackage(packageName),
                  duration_seconds = totalTimeInForeground.toInt(),
                  device = "mobile",
                  date = getCurrentDateString()
              )
          )
      }
  }
  ```

---

## 🔹 Synchronizing with the API

The Android Sync Agent (whether through a StayFree import script or a native Kotlin app) connects to the FastAPI backend using the following standard endpoint.

### 1. Endpoint: Bulk Ingest App Usage
- **URL**: `POST /api/app-usage/bulk`
- **Content-Type**: `application/json`

#### Example JSON Payload
```json
[
  {
    "app_name": "Instagram",
    "duration_seconds": 1800,
    "device": "mobile",
    "date": "2026-07-14",
    "timestamp": "2026-07-14T09:15:00Z"
  },
  {
    "app_name": "YouTube",
    "duration_seconds": 3600,
    "device": "mobile",
    "date": "2026-07-14",
    "timestamp": "2026-07-14T10:00:00Z"
  },
  {
    "app_name": "Duolingo",
    "duration_seconds": 900,
    "device": "mobile",
    "date": "2026-07-14",
    "timestamp": "2026-07-14T10:45:00Z"
  }
]
```

### 2. Endpoint: Record Screen Time
- **URL**: `POST /api/screen-time/`
- **Content-Type**: `application/json`

#### Example JSON Payload
```json
{
  "total_time_seconds": 6300,
  "device": "mobile",
  "date": "2026-07-14"
}
```
