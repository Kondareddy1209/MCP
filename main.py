from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlmodel import Session, select
import os

from db import init_db, get_session
from routers import expenses, app_usage, screen_time, classifications, analytics, events
from models import Expense, AppUsage, DailyScreenTime, AppClassification, ProductivityMetricsCache, UsageEvent

app = FastAPI(title="Antigravity API", description="Personal Intelligence System Backend")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to initialize DB
@app.on_event("startup")
def on_startup():
    init_db()

# Include Routers
app.include_router(expenses.router)
app.include_router(app_usage.router)
app.include_router(screen_time.router)
app.include_router(classifications.router)
app.include_router(analytics.router)
app.include_router(events.router)

@app.get("/api/ai-dashboard")
def get_ai_dashboard(days: int = 7, work_type: str = "developer", session: Session = Depends(get_session)):
    from analytics import generate_ai_dashboard
    return generate_ai_dashboard(session, days, work_type)


# Debug endpoint
@app.get("/debug/all-data")
def debug_all_data(session: Session = Depends(get_session)):
    return {
        "expenses": session.exec(select(Expense)).all(),
        "app_usage": session.exec(select(AppUsage)).all(),
        "daily_screen_time": session.exec(select(DailyScreenTime)).all(),
        "classifications": session.exec(select(AppClassification)).all(),
        "metrics_cache": session.exec(select(ProductivityMetricsCache)).all(),
        "usage_events": session.exec(select(UsageEvent)).all(),
    }

@app.get("/api/dashboard")
def get_dashboard_aggregate(days: int = 7, session: Session = Depends(get_session)):
    from analytics import calculate_analytics
    from sqlmodel import select
    from datetime import date, timedelta
    
    start_date = date.today() - timedelta(days=days)
    
    # 1. Fetch analytics
    data = calculate_analytics(session, days)
    
    # 2. Fetch parsed log alerts
    log_path = "interventions.log"
    alerts = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            for line in lines[-15:]:
                if "[INTERVENTION]" in line:
                    parts = line.split(" ")
                    timestamp = parts[0] + " " + parts[1].split(",")[0]
                    priority = parts[3].replace("[", "").replace("]", "")
                    message = " ".join(parts[4:]).strip()
                    alerts.append({
                        "timestamp": timestamp,
                        "priority": priority,
                        "message": message
                    })
        except Exception:
            pass
    alerts = alerts[::-1]
    
    # 3. Fetch recent events from DB
    events = session.exec(
        select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(20)
    ).all()
    
    # 4. Fetch raw data lists for Chart.js rendering and frontend calculations
    app_usages = session.exec(
        select(AppUsage).where(AppUsage.date >= start_date)
    ).all()
    
    screen_time_records = session.exec(
        select(DailyScreenTime).where(DailyScreenTime.date >= start_date)
    ).all()
    
    expenses_records = session.exec(
        select(Expense).where(Expense.date >= start_date)
    ).all()
    
    return {
        "analytics": data,
        "alerts": alerts,
        "events": events,
        "app_usage": app_usages,
        "screen_time": screen_time_records,
        "expenses": expenses_records
    }





# Serves Static Files
static_dir = os.path.join(os.path.dirname(__file__), "frontend")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    os.makedirs(os.path.join(static_dir, "components"), exist_ok=True)

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
                    timestamp = parts[0] + " " + parts[1].split(",")[0]
                    priority = parts[3].replace("[", "").replace("]", "")
                    message = " ".join(parts[4:]).strip()
                    alerts.append({
                        "timestamp": timestamp,
                        "priority": priority,
                        "message": message
                    })
        except Exception:
            pass
    return alerts[::-1]

@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to Antigravity API! Please create frontend/index.html to view dashboard."}

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

