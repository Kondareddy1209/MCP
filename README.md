<div align="center">

<h1>
  <img src="https://img.icons8.com/fluency/48/time-machine.png" width="36" style="vertical-align:middle"/> 
  it'syou
</h1>

<p><strong>Intelligent Screen Time & Productivity Tracker — powered by AI via MCP</strong></p>

<p>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-25_Tools-7C3AED?style=for-the-badge&logo=anthropic&logoColor=white" alt="MCP"/></a>
  <a href="https://www.sqlite.org"><img src="https://img.shields.io/badge/SQLite-Local_DB-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge" alt="License"/></a>
</p>

<p>
  <a href="#-about">About</a> •
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="#-mcp-ai-integration">MCP / AI</a> •
  <a href="#-real-world-use-cases">Use Cases</a> •
  <a href="#-contributing">Contributing</a>
</p>

<br/>

> **it'syou** is a local-first, AI-ready productivity system that passively tracks your desktop and mobile screen time, scores your focus, detects burnout, and lets your AI assistant (Claude, ChatGPT, Cursor, etc.) natively query and reason over your habits — all without any data ever leaving your machine.

</div>

---

## 🧠 About

Most productivity apps make you do the work — manually starting timers, tagging sessions, filling in forms. **it'syou** takes a different approach: it watches silently, learns your patterns, and gives both *you* and your *AI assistant* a live window into how you actually spend your time.

Built on top of the **Model Context Protocol (MCP)** — the open standard for connecting AI models to real-world tools — `it'syou` turns your personal usage data into a structured knowledge base that any MCP-compatible AI can query, summarize, and act on. Ask Claude *"How productive was I this week?"* and get a real, data-backed answer in seconds.

### Why it'syou?

- 🔒 **100% local** — your data never leaves your machine. No cloud. No subscriptions.
- 🤖 **AI-native** — the first screen-time tracker designed to work *with* AI assistants, not just report numbers to a dashboard.
- 🧩 **Extensible** — open source, modular Python backend. Add your own MCP tools, routers, and classifiers.
- 📱 **Cross-device** — unifies laptop + Android phone tracking in one timeline.
- 🔔 **Proactive** — doesn't just track; it intervenes. Smart alerts notify you before distraction becomes a habit.

---

## ✨ Features

### 📊 Real-Time Tracking
- Passive background monitoring of the active window (app name + window title)
- Event-driven session tracking: focus, blur, idle, and context-switch detection
- WebSocket-powered live dashboard — updates every second without refresh

### 🧠 Productivity Intelligence
- **Productivity Score (0–100)** based on classified app usage
- **Focus Efficiency %** — measures how long you stay in one context
- **Burnout Index (0–100)** — behavioral comparison vs. your 7-day baseline
- **Distraction Opportunity Cost** — quantifies time lost to distracting apps in hours or currency
- **Peak Hour Analysis** — identifies when you're most and least productive

### 🤖 MCP / AI Integration (25 Tools)
Connect any MCP-compatible AI assistant and ask questions like:
- *"What's my burnout risk right now?"*
- *"Which app wasted the most time today?"*
- *"Compare my productivity this week vs. last week."*
- *"Log a focus session for the next 45 minutes."*

### 🔔 Smart Interventions
- Adaptive intervention engine with configurable thresholds
- Web Push notifications (VAPID) — works on desktop browsers + mobile
- Smart cooldown: prevents notification fatigue with per-alert rate limiting
- Detects: excessive distraction, context-switch overload, late-night overwork, burnout risk

### 📱 Mobile Sync (Android ADB)
- Sync Android screen time directly via USB debug bridge
- Merges phone + laptop data into a unified daily timeline
- Per-app breakdowns from both devices in one dashboard

### 💰 Expense Tracker
- Log daily expenses by category
- Visualize spending patterns alongside productivity data

### 🏷️ App Classification
- Auto-classifies apps as **Productive / Neutral / Distracting** using regex heuristics
- Fully customizable — override any classification manually via the dashboard
- Supports both desktop process names and Android package names

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        it'syou System                          │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────┐  │
│  │   Desktop    │    │  FastAPI Server │    │  MCP Server   │  │
│  │   Tracker    │───▶│   (main.py)     │◀───│(mcp_server.py)│  │
│  │ (background) │    │  REST + WS API  │    │  25 AI Tools  │  │
│  └──────────────┘    └────────┬────────┘    └───────┬───────┘  │
│                               │                     │          │
│  ┌──────────────┐    ┌────────▼────────┐    ┌───────▼───────┐  │
│  │ Android ADB  │    │  SQLite DB      │    │  AI Assistant │  │
│  │ Mobile Sync  │───▶│(itsyou_clean.db)│    │ Claude/GPT/   │  │
│  └──────────────┘    └────────┬────────┘    │ Cursor etc.   │  │
│                               │             └───────────────┘  │
│  ┌──────────────┐    ┌────────▼────────┐                       │
│  │ Intervention │    │  Web Dashboard  │                       │
│  │   Engine     │    │  (frontend/)    │                       │
│  └──────────────┘    └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Repository Structure

```
it'syou/
├── main.py                     # FastAPI app — REST API + static frontend
├── mcp_server.py               # MCP server — 25 tools, 6 resources, 6 prompts
├── models.py                   # SQLModel schema (AppUsage, Events, Expenses …)
├── crud.py                     # Database CRUD with deduplication logic
├── classification.py           # App normalization + productivity classification
├── intervention_engine.py      # Adaptive alert engine (burnout, distraction)
├── db.py                       # Database engine + session factory
├── ws_manager.py               # WebSocket connection manager
├── config.json                 # Runtime feature flags
├── requirements.txt            # Python dependencies
│
├── services/
│   ├── analytics.py            # Cached analytics pipeline (single source of truth)
│   ├── notification_dispatch.py# VAPID Web Push dispatcher
│   ├── behavior_engine.py      # Burnout & behavior scoring engine
│   └── session_engine.py       # Session lifecycle management
│
├── routers/
│   ├── app_usage.py            # /api/app-usage/ endpoints
│   ├── analytics.py            # /api/dashboard/ endpoints
│   ├── events.py               # /api/events/ endpoints
│   ├── expenses.py             # /api/expenses/ endpoints
│   └── ...                     # additional routers
│
├── frontend/
│   ├── index.html              # Main dashboard HTML
│   ├── app.js                  # Frontend app logic
│   ├── components/
│   │   ├── dashboard.js        # Dashboard component
│   │   └── charts.js           # Chart rendering
│   ├── manifest.json           # PWA manifest
│   ├── sw.js                   # Service Worker (offline + push)
│   └── icon.svg                # App icon
│
├── scripts/
│   ├── mobile_adb_sync.py      # Android ADB screen time sync
│   └── generate_vapid_keys.py  # VAPID key generation for push notifications
│
├── tests/
│   ├── test_extended.py        # Core integration tests
│   └── test_mobile_adb_sync.py # ADB sync tests
│
└── docs/
    └── mobile_adb_setup.md     # Step-by-step Android ADB setup guide
```

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required |
| pip | latest | Required |
| Android phone | Any | Optional — for mobile sync |
| ADB (Android Debug Bridge) | Latest | Optional — for mobile sync |

### 1. Clone & Install

```bash
# Clone the repository
git clone https://github.com/Kondareddy1209/MCP.git
cd MCP

# Create a virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Install all dependencies
pip install -r requirements.txt
```

### 2. Run the Backend Server

```bash
python -m uvicorn main:app --reload --port 8000
```

Open **[http://localhost:8000](http://localhost:8000)** to view the live dashboard.

### 3. Run the MCP Server

```bash
python mcp_server.py
```

Then connect any MCP-compatible client (Claude Desktop, Cursor, etc.) to this server.

### 4. (Optional) Enable Additional Features

Edit `config.json`:

```json
{
  "run_intervention_engine": true,
  "run_mobile_sync": true
}
```

| Flag | Default | Effect |
|------|---------|--------|
| `run_intervention_engine` | `false` | Enables real-time burnout & distraction alerts |
| `run_mobile_sync` | `false` | Enables Android ADB phone sync |

### 5. (Optional) Set Up Push Notifications

```bash
# Generate VAPID keys for Web Push
python scripts/generate_vapid_keys.py
```

### 6. (Optional) Set Up Mobile Sync

See [`docs/mobile_adb_setup.md`](docs/mobile_adb_setup.md) for full Android ADB setup instructions.

---

## 🤖 MCP / AI Integration

`it'syou` implements the **Model Context Protocol** — the open standard by Anthropic that lets AI assistants call real tools and access structured data sources.

### Available MCP Tools (25 total)

| Tool | Description |
|------|-------------|
| `get_dashboard_metrics` | Full analytics for last N days |
| `get_current_activity` | Currently active app and focus durations |
| `get_productivity_score` | Productivity score + breakdown |
| `get_focus_efficiency` | Focus %, longest session, context switches |
| `get_burnout_index` | Burnout risk score (0–100) |
| `get_distraction_cost` | Opportunity cost from distraction |
| `get_behavioral_insights` | Peak hours, top apps, switch analysis |
| `get_recent_events` | Raw focus/blur/idle event log |
| `get_screen_time_history` | Daily/hourly screen time records |
| `classify_app` | Get or set an app's productivity category |
| `add_expense` | Log a new expense entry |
| `get_expenses` | Retrieve expense history |
| `...` | + 13 more tools for full system control |

### Connecting Claude Desktop

Add this to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "itsyou": {
      "command": "python",
      "args": ["C:/path/to/MCP/mcp_server.py"]
    }
  }
}
```

---

## 🌍 Real-World Use Cases

| Who | How they use it'syou |
|-----|---------------------|
| **Developers** | Track IDE vs. browser vs. Slack time; identify context-switch overload |
| **Students** | Monitor study vs. entertainment balance; get focus alerts |
| **Freelancers** | Log billable hours per app; export productivity reports |
| **Remote workers** | Prove work hours to clients with data-backed productivity scores |
| **Deep work practitioners** | Get notified when focus sessions break; track longest focus streaks |
| **AI power users** | Ask Claude/GPT to analyze habits and suggest schedule improvements |
| **Parents** | Monitor their own device usage as a digital wellness practice |

---

## 🚨 Problems it'syou Solves

| Problem | Solution |
|---------|----------|
| *"Where did my day go?"* | Passive auto-tracking — no timers, no manual input |
| Mindless app switching | Detects context-switch overload and fires alerts |
| No cross-device visibility | Unifies laptop + Android phone in one timeline |
| Burnout going unnoticed | Compares today vs. 7-day behavioral baseline |
| AI assistants can't see your habits | MCP server exposes your data as structured AI tools |
| Cloud tracker privacy concerns | 100% local SQLite — zero telemetry, zero cloud |
| Notification overload | Per-alert cooldown prevents duplicate alerts |
| Inaccurate timezone in logs | All data stored in IST (Asia/Kolkata) for local accuracy |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Database** | SQLite (local) via SQLModel |
| **AI Protocol** | Model Context Protocol (MCP) |
| **Frontend** | HTML5, Vanilla JS, CSS3, WebSocket |
| **PWA** | Service Worker, Web App Manifest |
| **Mobile** | Android Debug Bridge (ADB) |
| **Push Notifications** | Web Push API, VAPID (`pywebpush`, `py-vapid`) |
| **Analytics** | Pandas, in-memory analytics cache |
| **Timezone** | IST (Asia/Kolkata) throughout |

---

## 🧪 Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_extended.py -v
```

---

## 🤝 Contributing

Contributions are very welcome! Here's how to get started:

1. **Fork** the repository
2. **Create** your feature branch: `git checkout -b feature/your-feature`
3. **Commit** your changes: `git commit -m "feat: add your feature"`
4. **Push** to the branch: `git push origin feature/your-feature`
5. **Open a Pull Request**

Please follow the existing code style and add tests where applicable.

---

## 📄 License

This project is licensed under the **MIT License** — free to use, modify, and distribute.

---

## 👤 Author

**Konda Reddy**
- GitHub: [@Kondareddy1209](https://github.com/Kondareddy1209)

---

<div align="center">

**⭐ Star this repo if you find it useful!**

*Built with ❤️ for developers who want to own their time — and their data.*

</div>
