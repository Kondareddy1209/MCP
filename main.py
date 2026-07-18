"""
main.py — it'syou API
Database: itsyou_clean.db (single source of truth)
All timestamps: IST (Asia/Kolkata, UTC+5:30)
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlmodel import Session, select, text
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta, datetime, timezone

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


TRACKER_INSTANCE = None

@asynccontextmanager
async def lifespan(app_: FastAPI):
    """Application lifespan: startup → yield → (shutdown if needed)."""
    # ── DB init & indexes ─────────────────────────────────────────────────
    init_db()
    print(f"[startup] Database initialized: itsyou_clean.db")
    print(f"[startup] IST time: {ist_now().strftime('%Y-%m-%d %H:%M:%S %Z')}")

    session = next(get_session())
    try:
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON app_usage(timestamp);"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON usage_events(timestamp);"))
        session.commit()
        print("[startup] Database indexes verified/created.")
    except Exception as e:
        print(f"[startup] Index verification error: {e}")

    # ── Auto-start desktop tracker ────────────────────────────────────────
    from threading import Thread
    try:
        from scripts.desktop_tracker import ItsYouTracker, IS_WINDOWS
        if IS_WINDOWS:
            global TRACKER_INSTANCE
            TRACKER_INSTANCE = ItsYouTracker(api_url="http://localhost:8000/api")
            thread = Thread(target=TRACKER_INSTANCE.run, daemon=True)
            thread.start()
            print("[startup] Background desktop tracker thread started.")
        else:
            print("[startup] Desktop tracker not started: non-Windows OS.")
    except Exception as e:
        print(f"[startup] Failed to start desktop tracker: {e}")

    # ── Auto-start intervention engine (config-gated) ─────────────────────
    try:
        import json as _json
        _cfg = {}
        if os.path.exists("config.json"):
            with open("config.json", "r") as _f:
                _cfg = _json.load(_f)
        if _cfg.get("run_intervention_engine", False):
            from intervention_engine import InterventionEngine
            _ie = InterventionEngine(check_interval_seconds=60)
            _ie_thread = Thread(target=_ie.start_monitoring, daemon=True)
            _ie_thread.start()
            print("[startup] Intervention engine started as daemon thread.")
        else:
            print("[startup] Intervention engine disabled (set run_intervention_engine=true in config.json to enable).")
    except Exception as e:
        print(f"[startup] Intervention engine start error: {e}")

    yield
    # shutdown: daemon threads die with the process; nothing to clean up here



app = FastAPI(
    title="it'syou API",
    description="Personal Intelligence System Backend",
    version="2.0.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return calculate_analytics(session, days)


# ─── Conversational Behavioral Analysis ──────────────────────────────────────
@app.get("/api/explain")
@app.post("/api/explain")
def explain_endpoint(
    question: str = "Why was my productivity lower today?",
    days: int = 1,
    session: Session = Depends(get_session)
):
    """Conversational behavioral analysis: compares current vs prior period metrics.

    Returns a structured JSON response with:
    - explanation: natural-language summary (deterministic, no LLM)
    - primary_driver: the single largest factor driving the change
    - drivers: all identified deltas ranked by magnitude
    - metrics_today / metrics_prior: raw metric values for each window
    """
    from services.analytics import explain_productivity_change
    return explain_productivity_change(session, question=question, days=days)


from fastapi import WebSocket, WebSocketDisconnect
from ws_manager import manager

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, discard incoming client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket] Disconnected with error: {e}")
        manager.disconnect(websocket)

from pydantic import BaseModel

class IngestPayload(BaseModel):
    device: str
    app: str
    timestamp: str
    duration: int

@app.get("/api/last-active-app")
def get_last_active_app(session: Session = Depends(get_session)):
    IGNORE_APPS = [
        "ItsYouTrackerDaemon", "itsyoutrackerdaemon", "tracker.exe", "TRACKER.EXE",
        "python.exe", "PYTHON.EXE", "uvicorn.exe", "UVICORN.EXE",
        "cmd.exe", "CMD.EXE", "powershell.exe", "POWERSHELL.EXE"
    ]
    event = session.exec(
        select(UsageEvent)
        .where(~UsageEvent.app_name.in_(IGNORE_APPS))
        .order_by(UsageEvent.timestamp.desc())
        .limit(1)
    ).first()
    if event:
        status = "inactive" if event.event_type in ["blur", "IDLE_START", "SESSION_END"] else "active"
        return {
            "app": event.app_name or "Unknown",
            "window": event.window_title or "Unknown",
            "timestamp": event.timestamp.isoformat(),
            "status": status
        }
    return {
        "app": "None",
        "window": "None",
        "timestamp": "",
        "status": "inactive"
    }

@app.get("/api/live-usage")
def get_live_usage(session: Session = Depends(get_session)):
    last_app = get_last_active_app(session)
    today = ist_now().date()
    usages = session.exec(
        select(AppUsage).where(AppUsage.date == today)
    ).all()
    
    app_summary = {}
    for u in usages:
        app_summary[u.app_name] = app_summary.get(u.app_name, 0) + u.duration_seconds
        
    events_list = session.exec(
        select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(10)
    ).all()
    
    event_list = [{
        "id": e.id,
        "event_type": e.event_type,
        "app_name": e.app_name,
        "window_title": e.window_title,
        "timestamp": e.timestamp.isoformat()
    } for e in events_list]
    
    return {
        "last_active": last_app,
        "today_summary": app_summary,
        "recent_events": event_list
    }

@app.post("/api/ingest")
def ingest_data(payload: IngestPayload, session: Session = Depends(get_session)):
    try:
        # Normalize and parse timestamp
        ts_str = payload.timestamp.replace("Z", "")
        if "T" not in ts_str and " " in ts_str:
            ts_str = ts_str.replace(" ", "T")
        ts = datetime.fromisoformat(ts_str)
    except Exception:
        ts = ist_now()
        
    # Coerce to IST if naive
    if ts.tzinfo is None:
        try:
            ts = ts.replace(tzinfo=pytz.timezone("Asia/Kolkata"))
        except Exception:
            ts = ts.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        
    from classification import normalize_app_name
    normalized_app = normalize_app_name(payload.app)

    app_usage = AppUsage(
        app_name=normalized_app,
        duration_seconds=payload.duration,
        device=payload.device,
        device_type="mobile" if payload.device == "mobile" else "desktop",
        date=ts.date(),
        timestamp=ts
    )
    
    from crud import create_app_usage
    created = create_app_usage(session, app_usage)
    from services.analytics import invalidate_analytics_cache
    invalidate_analytics_cache()
    return {"status": "success", "id": created.id}


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


# ─── Tracker Control Endpoints (Task 11 & Phase 2) ────────────────────────
@app.post("/api/tracker/pause")
def pause_tracker():
    global TRACKER_INSTANCE
    if TRACKER_INSTANCE:
        TRACKER_INSTANCE.paused = True
        return {"status": "success", "message": "Tracker paused"}
    return {"status": "error", "message": "Tracker not running"}

@app.post("/api/tracker/resume")
def resume_tracker():
    global TRACKER_INSTANCE
    if TRACKER_INSTANCE:
        TRACKER_INSTANCE.paused = False
        return {"status": "success", "message": "Tracker resumed"}
    return {"status": "error", "message": "Tracker not running"}

@app.post("/api/tracker/stop")
def stop_tracker_endpoint():
    global TRACKER_INSTANCE
    if TRACKER_INSTANCE:
        TRACKER_INSTANCE.paused = True
        if hasattr(TRACKER_INSTANCE, "input_tracker") and TRACKER_INSTANCE.input_tracker:
            TRACKER_INSTANCE.input_tracker.stop()
        return {"status": "success", "message": "Tracker stopped"}
    return {"status": "error", "message": "Tracker not running"}

@app.post("/api/tracker/start")
def start_tracker_endpoint():
    global TRACKER_INSTANCE
    if TRACKER_INSTANCE:
        TRACKER_INSTANCE.paused = False
        if hasattr(TRACKER_INSTANCE, "input_tracker") and TRACKER_INSTANCE.input_tracker:
            try:
                TRACKER_INSTANCE.input_tracker.start()
            except Exception:
                pass  # already started or inactive
        return {"status": "success", "message": "Tracker started/resumed"}
    else:
        from threading import Thread
        from scripts.desktop_tracker import ItsYouTracker
        TRACKER_INSTANCE = ItsYouTracker(api_url="http://localhost:8000/api")
        thread = Thread(target=TRACKER_INSTANCE.run, daemon=True)
        thread.start()
        return {"status": "success", "message": "Tracker initialized and started"}

@app.get("/api/tracker/status")
def get_tracker_status():
    global TRACKER_INSTANCE
    if not TRACKER_INSTANCE:
        return {"status": "stopped", "paused": True, "session_id": None}
    return {
        "status": "paused" if TRACKER_INSTANCE.paused else "running",
        "paused": TRACKER_INSTANCE.paused,
        "session_id": TRACKER_INSTANCE.session_id,
        "current_app": TRACKER_INSTANCE.current_app,
        "is_idle": TRACKER_INSTANCE.is_idle
    }


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
