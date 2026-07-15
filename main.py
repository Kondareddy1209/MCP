"""
main.py — it'syou API
Database: itsyou_clean.db (single source of truth)
All timestamps: IST (Asia/Kolkata, UTC+5:30)
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlmodel import Session, select
import os
from datetime import date, timedelta, datetime, timezone, timedelta

from db import init_db, get_session
from routers import expenses, app_usage, screen_time, classifications, analytics, events
from models import Expense, AppUsage, DailyScreenTime, AppClassification, ProductivityMetricsCache, UsageEvent

# ─── IST helper ─────────────────────────────────────────────────────────
try:
    import pytz
    _IST = pytz.timezone("Asia/Kolkata")
    def ist_now() -> datetime:
        return datetime.now(_IST)
except ImportError:
    _IST_OFFSET = timezone(timedelta(hours=5, minutes=30))
    def ist_now() -> datetime:
        return datetime.now(_IST_OFFSET)


app = FastAPI(title="it'syou API", description="Personal Intelligence System Backend", version="2.0.0")

# ─── CORS ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Startup: create tables in itsyou_clean.db ───────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    print(f"[startup] Database initialized: itsyou_clean.db")
    print(f"[startup] IST time: {ist_now().strftime('%Y-%m-%d %H:%M:%S %Z')}")

# ─── Routers ─────────────────────────────────────────────────────────────
app.include_router(expenses.router)
app.include_router(app_usage.router)
app.include_router(screen_time.router)
app.include_router(classifications.router)
app.include_router(analytics.router)
app.include_router(events.router)


# ─── AI Dashboard ────────────────────────────────────────────────────────
@app.get("/api/ai-dashboard")
def get_ai_dashboard(days: int = 7, work_type: str = "developer", session: Session = Depends(get_session)):
    from analytics import generate_ai_dashboard
    return generate_ai_dashboard(session, days, work_type)


# ─── Debug: raw DB dump ──────────────────────────────────────────────────
@app.get("/debug/all-data")
def debug_all_data(session: Session = Depends(get_session)):
    return {
        "database": "itsyou_clean.db",
        "expenses": session.exec(select(Expense)).all(),
        "app_usage": session.exec(select(AppUsage)).all(),
        "daily_screen_time": session.exec(select(DailyScreenTime)).all(),
        "classifications": session.exec(select(AppClassification)).all(),
        "metrics_cache": session.exec(select(ProductivityMetricsCache)).all(),
        "usage_events": session.exec(select(UsageEvent)).all(),
    }


# ─── Main Dashboard Aggregate ─────────────────────────────────────────────
@app.get("/api/dashboard")
def get_dashboard_aggregate(days: int = 7, session: Session = Depends(get_session)):
    from analytics import calculate_analytics

    # IST today date
    today = ist_now().date()

    # ✅ STEP 7: No fallbacks — query real data only
    # For days=1: return ONLY today's records
    # For days=N: return last N days starting from today
    if days == 1:
        start_date = today
    else:
        start_date = today - timedelta(days=days - 1)

    # Analytics computation
    try:
        analytics_data = calculate_analytics(session, days)
    except Exception as e:
        print(f"[dashboard] analytics error: {e}")
        analytics_data = {}

    # Alerts from log file
    log_path = "interventions.log"
    alerts = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            for line in lines[-15:]:
                if "[INTERVENTION]" in line:
                    parts = line.split(" ")
                    if len(parts) >= 4:
                        timestamp = parts[0] + " " + parts[1].split(",")[0]
                        priority = parts[3].replace("[", "").replace("]", "")
                        message = " ".join(parts[4:]).strip()
                        alerts.append({"timestamp": timestamp, "priority": priority, "message": message})
        except Exception:
            pass
    alerts = alerts[::-1]

    # Fetch data from itsyou_clean.db only
    events_list = session.exec(
        select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(20)
    ).all()

    app_usages = session.exec(
        select(AppUsage).where(AppUsage.date >= start_date).order_by(AppUsage.date.desc())
    ).all()

    screen_time_records = session.exec(
        select(DailyScreenTime).where(DailyScreenTime.date >= start_date)
    ).all()

    expenses_records = session.exec(
        select(Expense).where(Expense.date >= start_date)
    ).all()

    return {
        "analytics": analytics_data,
        "alerts": alerts,
        "events": events_list,
        "app_usage": app_usages,
        "screen_time": screen_time_records,
        "expenses": expenses_records,
        # ✅ STEP 7: meta always reflects real state — no mock values
        "meta": {
            "database": "itsyou_clean.db",
            "days": days,
            "start_date": str(start_date),
            "today_ist": str(today),
            "server_time_ist": ist_now().strftime("%Y-%m-%d %H:%M:%S"),
            "record_count": len(app_usages),
            "has_today_data": any(str(u.date) == str(today) for u in app_usages)
        }
    }


# ─── Alerts endpoint ──────────────────────────────────────────────────────
@app.get("/api/alerts")
def get_alerts():
    log_path = "interventions.log"
    alerts = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            for line in lines[-15:]:
                if "[INTERVENTION]" in line:
                    parts = line.split(" ")
                    if len(parts) >= 4:
                        timestamp = parts[0] + " " + parts[1].split(",")[0]
                        priority = parts[3].replace("[", "").replace("]", "")
                        message = " ".join(parts[4:]).strip()
                        alerts.append({"timestamp": timestamp, "priority": priority, "message": message})
        except Exception:
            pass
    return alerts[::-1]


# ─── Static file serving ──────────────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "frontend")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(os.path.join(static_dir, "components"), exist_ok=True)

@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "it'syou API v2.0 — visit /docs for API reference"}

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
