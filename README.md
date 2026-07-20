# it'syou — Intelligent Screen Time & Productivity Tracker

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-purple.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **it'syou** is a local-first, AI-ready personal productivity tracker that silently monitors your desktop and mobile screen time in real time — then lets your AI assistant (Claude, GPT, etc.) query, analyze, and intervene on your behalf through the **Model Context Protocol (MCP)**.

---

## 📌 What Is This Repository?

This repo is the **backend + MCP server** for the `it'syou` productivity tracking system. It runs entirely on your local machine, stores all data in a local SQLite database, and exposes:

- A **FastAPI REST backend** (`main.py`) for the web dashboard
- A **Model Context Protocol (MCP) server** (`mcp_server.py`) with 25 tools, 6 resources, and 6 prompts — so AI assistants can talk to your screen-time data
- A **real-time desktop tracker** that automatically captures which apps you use and for how long
- An **intervention engine** that fires smart alerts when you've been distracted too long or show signs of burnout
- A **mobile sync module** via Android ADB to pull phone usage data alongside laptop data

---

## 🗂️ What Does This Repo Include?

| Module | Description |
|--------|-------------|
| `main.py` | FastAPI application — REST API + static frontend server |
| `mcp_server.py` | MCP server exposing 25 tools for AI assistant integration |
| `models.py` | SQLModel database schema (AppUsage, Expenses, Events, etc.) |
| `crud.py` | Database CRUD operations with deduplication logic |
| `classification.py` | App name normalization + productivity classification |
| `intervention_engine.py` | Adaptive alert engine (burnout, distraction, overwork detection) |
| `services/analytics.py` | Centralized cached analytics pipeline |
| `services/notification_dispatch.py` | Web Push notification dispatcher (VAPID) |
| `scripts/mobile_adb_sync.py` | Android phone screen time sync via ADB |
| `scripts/generate_vapid_keys.py` | VAPID key generator for push notifications |
| `frontend/` | Vanilla JS + HTML dashboard with real-time WebSocket updates |
| `tests/` | Unit and integration tests |
| `docs/` | Documentation for ADB mobile setup |

---

## 🌍 Real-World Use Cases

### 👩‍💻 Developers & Knowledge Workers
Track which IDEs, browsers, and communication tools you're actually using — and for how long. Understand where your workday really goes.

### 🎯 Deep Work Practitioners
Get automatic alerts when you drift into distraction (YouTube, Reddit, Instagram) for too long, helping you reclaim focus without needing manual timers.

### 📱 Multi-Device Users
Sync both your laptop and Android phone usage into a single unified timeline. See your true total screen time across all devices.

### 🤖 AI Assistant Power Users
Because this runs an **MCP server**, you can ask Claude or any MCP-compatible AI things like:
- *"How productive was I this week?"*
- *"Which app wasted the most time today?"*
- *"Am I showing signs of burnout based on my recent patterns?"*
- *"Summarize my work habits for the last 30 days."*

### 💼 Freelancers & Remote Workers
Track billable hours per application and project, log expenses, and get productivity scores to share with clients or use for self-review.

---

## 🚨 Problems This Solves

| Problem | How it'syou Solves It |
|---------|----------------------|
| **"Where did my day go?"** | Automatic passive tracking — no manual timers needed |
| **Mindless app switching** | Detects distraction patterns and fires intervention alerts |
| **No unified cross-device view** | Merges laptop + Android phone data via ADB |
| **Burnout going unnoticed** | Behavioral engine compares today vs. 7-day baseline to detect overwork |
| **AI can't see your habits** | MCP server lets AI assistants directly query your usage data |
| **Privacy concerns with cloud trackers** | 100% local — all data stays on your machine in a local SQLite DB |
| **Push notification fatigue** | Smart cooldown system prevents duplicate/spammy alerts |
| **Timezone-incorrect logs** | All timestamps are stored in IST (Asia/Kolkata) for accurate local reporting |

---

## 🛠️ Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn
- **Database:** SQLite via SQLModel (local, no cloud)
- **AI Integration:** Model Context Protocol (MCP) — compatible with Claude Desktop, Cursor, and any MCP client
- **Frontend:** Vanilla JS, HTML/CSS, WebSocket for real-time updates
- **Mobile Sync:** Android Debug Bridge (ADB)
- **Push Notifications:** Web Push API with VAPID keys (`pywebpush`)
- **Analytics:** Pandas, cached dashboard pipeline

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- (Optional) Android phone with USB debugging enabled, for mobile sync

### Installation

```bash
# Clone the repository
git clone https://github.com/Kondareddy1209/MCP.git
cd MCP

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Run the Server

```bash
python -m uvicorn main:app --reload --port 8000
```

Open your browser at [http://localhost:8000](http://localhost:8000) to view the dashboard.

### Run the MCP Server (for AI Assistant Integration)

```bash
python mcp_server.py
```

Configure your MCP client (e.g., Claude Desktop) to connect to this server.

### Enable Mobile Sync (Optional)

See [`docs/mobile_adb_setup.md`](docs/mobile_adb_setup.md) for step-by-step ADB setup.

### Generate VAPID Keys (for Push Notifications)

```bash
python scripts/generate_vapid_keys.py
```

---

## ⚙️ Configuration

Edit `config.json` to enable/disable optional features:

```json
{
  "run_intervention_engine": false,
  "run_mobile_sync": false
}
```

Set both to `true` to enable real-time alerts and mobile data sync.

---

## 📊 Dashboard Features

- **Real-time active app tracking** via WebSocket
- **Daily / Weekly / Monthly** productivity breakdowns
- **App classification** (Productive / Neutral / Distracting) — auto-detected or manually set
- **Productivity score** (0–100) based on your usage patterns
- **Expense tracking** with category breakdown
- **Burnout & distraction alerts** via push notifications

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues, suggest features, or submit pull requests.

---

## 📄 License

MIT License — free to use and modify.
