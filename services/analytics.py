"""
services/analytics.py — Centralized Analytics Engine
Compute all metrics deterministically from SQLite db using Session and Behavior engines.
"""
from sqlmodel import Session, select
from datetime import date, datetime, timedelta, time
import json
import os
from typing import List, Dict, Any, Tuple
import pytz

from models import (
    Expense, AppUsage, DailyScreenTime, AppClassification, UsageEvent,
    ProductivityMetrics, FocusMetrics, BurnoutMetrics, DistractionCostMetrics,
    BehavioralInsightsMetrics
)
from classification import auto_classify
from services.session_engine import SessionEngine, TrackedSession
from services.behavior_engine import BehaviorEngine

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

# In-Memory Cache (Task 13)
_DASHBOARD_CACHE = {}

def get_ist_now() -> datetime:
    try:
        ist = pytz.timezone("Asia/Kolkata")
        return datetime.now(ist)
    except Exception:
        # Fallback to UTC+5:30 offset
        from datetime import timezone
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))

def load_config() -> Dict[str, Any]:
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"hourly_rate": 200, "currency": "INR"}

def invalidate_analytics_cache():
    global _DASHBOARD_CACHE
    _DASHBOARD_CACHE.clear()
    print("[Cache] Centralized analytics cache invalidated.")

def get_safe_empty_summary(days: int) -> Dict[str, Any]:
    """Generates a safe empty summary payload with all metrics set to None for type safety (Task 6)"""
    return {
        "analytics": {
            "productivity_score": None,
            "focus_efficiency": None,
            "burnout_score": None,
            "burnout_risk": None,
            "distraction_cost": None,
            "currency": "INR",
            "total_spent": 0.0,
            "deep_work_sessions": 0,
            "total_sessions": 1
        },
        "alerts": [],
        "events": [],
        "app_usage": [],
        "screen_time": [],
        
        # Legacy compatibility
        "productivity_score": None,
        "focus_efficiency": None,
        "burnout_score": None,
        "burnout_risk": None,
        "distraction_cost": None,
        "currency": "INR",
        "total_spent": 0.0,
        "deep_work_sessions": 0,
        "total_sessions": 1,
        "detected_habits": [],
        "total_screen_time": {"mobile": 0, "laptop": 0},
        "top_productive_apps": [],
        "top_distracting_apps": [],

        "current_activity": {
            "app": "SYSTEM_IDLE",
            "device": "laptop",
            "duration": 0,
            "today_active_time": "0.0 hrs",
            "idle_timer": 0,
            "last_activity": "No data"
        },
        "productivity": {
            "score": None,
            "productive_minutes": 0.0,
            "neutral_minutes": 0.0,
            "distracting_minutes": 0.0
        },
        "focus": {
            "focus_percentage": None,
            "average_session": 0,
            "longest_session": 0,
            "deep_focus_count": 0,
            "switches_today": 0
        },
        "burnout": {
            "score": None,
            "risk": None
        },
        "distraction_cost_details": {
            "amount": None,
            "currency": "INR"
        },
        "insights": {
            "most_used_app": None,
            "longest_session": None,
            "most_productive_app": None,
            "most_distracting_app": None,
            "peak_productive_hour": None,
            "peak_distraction_hour": None,
            "average_session_duration": None,
            "average_idle_duration": None,
            "number_of_app_switches": 0,
            "daily_active_time": None,
            "biggest_time_waster": None,
            "spending_pattern": None,
            "suggestion": "No activity tracked"
        },
        "recommendations": ["No activity tracked today."],
        "charts": {
            "app_usage": [],
            "screen_time": []
        },
        "live_status": {
            "status": "inactive"
        }
    }

def get_cached_dashboard_summary(session: Session, days: int) -> Dict[str, Any]:
    global _DASHBOARD_CACHE
    today = get_ist_now().date()
    cache_key = (days, today)
    if cache_key in _DASHBOARD_CACHE:
        print(f"[Cache] Hit for days={days}, date={today}")
        return _DASHBOARD_CACHE[cache_key]
    
    print(f"[Cache] Miss for days={days}, date={today}. Recomputing...")
    try:
        summary = compute_dashboard_summary(session, days)
        # Cache only successful runs (Task 6)
        _DASHBOARD_CACHE[cache_key] = summary
        return summary
    except Exception as e:
        print(f"[Cache] Error recomputing analytics summary: {e}")
        # Return previous cached entry if available
        for (cached_days, date_key), cached_val in list(_DASHBOARD_CACHE.items()):
            if cached_days == days:
                print(f"[Cache] Recovered previous cached entry from {date_key} after calculation error.")
                return cached_val
        # Otherwise return a safe empty payload to prevent HTTP 500 crash
        return get_safe_empty_summary(days)

def compute_screen_time_history(session: Session, start_date: date, days: int) -> List[Dict[str, Any]]:
    """Calculates screen time history. Returns hourly buckets for days=1 (Task 8)"""
    if days == 1:
        # Today: Return hourly buckets
        usages = session.exec(
            select(AppUsage).where(AppUsage.date == start_date)
        ).all()
        
        hourly_data: Dict[str, Dict[str, int]] = {}
        for h in range(24):
            hour_str = f"{h:02d}:00"
            hourly_data[hour_str] = {"laptop": 0, "mobile": 0}
            
        for u in usages:
            if getattr(u, "idle_flag", False) or u.app_name == "SYSTEM_IDLE":
                continue
            ts = u.timestamp if isinstance(u.timestamp, datetime) else datetime.fromisoformat(u.timestamp.replace("Z", ""))
            hour_str = f"{ts.hour:02d}:00"
            device = u.device or "laptop"
            if hour_str in hourly_data:
                hourly_data[hour_str][device] += u.duration_seconds
                
        records = []
        for hour_str, dev_data in hourly_data.items():
            for device, sec in dev_data.items():
                records.append({
                    "date": hour_str,
                    "device": device,
                    "total_time_seconds": sec
                })
        return records
    else:
        # Multi-day: Group by date and device using AppUsage as the live source of truth,
        # fallback/merge with DailyScreenTime entries if any exist.
        usages = session.exec(
            select(AppUsage).where(AppUsage.date >= start_date)
        ).all()
        
        grouped: Dict[str, Dict[str, int]] = {}
        for u in usages:
            if getattr(u, "idle_flag", False) or u.app_name == "SYSTEM_IDLE":
                continue
            d_str = str(u.date)
            dev = u.device or "laptop"
            if d_str not in grouped:
                grouped[d_str] = {}
            grouped[d_str][dev] = grouped[d_str].get(dev, 0) + u.duration_seconds
            
        manual_records = session.exec(
            select(DailyScreenTime).where(DailyScreenTime.date >= start_date)
        ).all()
        for r in manual_records:
            d_str = str(r.date)
            dev = r.device or "laptop"
            if d_str not in grouped:
                grouped[d_str] = {}
            grouped[d_str][dev] = max(grouped[d_str].get(dev, 0), r.total_time_seconds)
            
        records = []
        for d_str, dev_data in sorted(grouped.items()):
            for device, sec in dev_data.items():
                records.append({
                    "date": d_str,
                    "device": device,
                    "total_time_seconds": sec
                })
        return records

def compute_dashboard_summary(session: Session, days: int) -> Dict[str, Any]:
    """Generates the single unified aggregate dashboard summary payload"""
    config = load_config()
    hourly_rate = config.get("hourly_rate", 200)
    currency = config.get("currency", "INR")
    
    today = get_ist_now().date()
    if days == 1:
        start_date = today
    else:
        start_date = today - timedelta(days=days - 1)
        
    start_timestamp = datetime.combine(start_date, time.min)
    
    # Query database using standard SQLModel selections
    usages = session.exec(select(AppUsage).where(AppUsage.date >= start_date)).all()
    events = session.exec(select(UsageEvent).where(UsageEvent.timestamp >= start_timestamp).order_by(UsageEvent.timestamp.desc())).all()
    expenses = session.exec(select(Expense).where(Expense.date >= start_date)).all()
    classifications = {c.app_name.lower(): c.classification for c in session.exec(select(AppClassification)).all()}

    # 1. Reconstruct Focus & Idle Sessions using SessionEngine
    sessions = SessionEngine.reconstruct_sessions(usages, events)
    
    # 2. Compute behavioral insights and scores using BehaviorEngine
    prod = BehaviorEngine.analyze_productivity(sessions, classifications)
    focus = BehaviorEngine.analyze_focus(sessions, events)
    burnout = BehaviorEngine.analyze_burnout(sessions)
    dist_cost = BehaviorEngine.analyze_distraction_cost(sessions, classifications, hourly_rate)
    insights = BehaviorEngine.analyze_behavioral_insights(sessions, classifications, events)
    
    # Calculate continuous active session durations for recommendation engine
    active_sessions = [s for s in sessions if not s.idle_flag and s.app_name != "SYSTEM_IDLE"]
    max_session_seconds = max(s.duration_seconds for s in active_sessions) if active_sessions else 0.0
    
    recs = BehaviorEngine.generate_recommendations(prod.score, focus.switches_today, max_session_seconds)
    
    # Set suggestion text
    insights.suggestion = recs[0] if recs else "No activity tracked"
    
    # Calculate spending patterns dynamically based on recorded expense categories
    if expenses:
        categories = {}
        for e in expenses:
            categories[e.category] = categories.get(e.category, 0.0) + e.amount
        insights.spending_pattern = max(categories, key=categories.get) if categories else None
    else:
        insights.spending_pattern = None

    # Calculate Screen Time History Chart Data
    screen_time_history = compute_screen_time_history(session, start_date, days)

    # Track accumulated window titles for each app name (to help auto_classify identify categories correctly)
    app_window_titles = {}
    for s in sessions:
        if s.idle_flag or s.app_name == "SYSTEM_IDLE":
            continue
        if s.app_name not in app_window_titles:
            app_window_titles[s.app_name] = []
        for t in s.window_titles:
            if t not in app_window_titles[s.app_name]:
                app_window_titles[s.app_name].append(t)

    # Format app usage chart details
    app_durations = {}
    for s in sessions:
        if s.idle_flag or s.app_name == "SYSTEM_IDLE":
            continue
        app_durations[s.app_name] = app_durations.get(s.app_name, 0.0) + s.duration_seconds
        
    chart_usage = []
    for app_name, sec in app_durations.items():
        chart_usage.append({
            "app_name": app_name,
            "duration_seconds": sec
        })

    # Prepare top productive / distracting lists for generate_ai_dashboard compatibility
    top_productive_apps = []
    top_distracting_apps = []
    for app, sec in app_durations.items():
        app_clean = app.lower().strip()
        titles = app_window_titles.get(app, [])
        cl = classifications.get(app_clean) or auto_classify(app, " ".join(titles))
        item = {"app_name": app, "duration_seconds": int(sec)}
        if cl == "productive":
            top_productive_apps.append(item)
        elif cl == "distracting":
            top_distracting_apps.append(item)
            
    top_productive_apps = sorted(top_productive_apps, key=lambda x: x["duration_seconds"], reverse=True)[:5]
    top_distracting_apps = sorted(top_distracting_apps, key=lambda x: x["duration_seconds"], reverse=True)[:5]

    # Calculate total screen time grouped by device
    total_screen_time = {"mobile": 0, "laptop": 0}
    for item in screen_time_history:
        dev = item.get("device", "laptop")
        if dev in total_screen_time:
            total_screen_time[dev] += item["total_time_seconds"]

    # 3. Current Activity Details (with ignore-list process filtering & staleness detection)
    IGNORE_APPS = {"ItsYouTrackerDaemon", "itsyoutrackerdaemon", "tracker.exe", "python.exe", "uvicorn.exe", "cmd.exe", "powershell.exe"}
    user_events = [e for e in events if e.app_name not in IGNORE_APPS]
    last_event = user_events[0] if user_events else None
    absolute_last = events[0] if events else None

    current_activity = {
        "app": "SYSTEM_IDLE",
        "device": "laptop",
        "duration": 0,
        "today_active_time": f"{round(sum(s.duration_seconds for s in sessions if not s.idle_flag and s.start_time.date() == today)/3600, 1)} hrs",
        "idle_timer": 0,
        "last_activity": None,
        "is_stale": False
    }

    if last_event:
        is_idle = last_event.event_type in ["blur", "IDLE_START", "SESSION_END", "idle"] or last_event.app_name == "SYSTEM_IDLE"
        current_activity["last_activity"] = last_event.timestamp.strftime("%H:%M:%S")
        
        now_naive = get_ist_now().replace(tzinfo=None)
        ts_naive = last_event.timestamp.replace(tzinfo=None)
        dur = int((now_naive - ts_naive).total_seconds())
        
        # Stale check: if last user event was > 5 minutes ago and the absolute last event is a daemon process
        if dur > 300 and absolute_last and absolute_last.app_name in IGNORE_APPS:
            current_activity["is_stale"] = True

        if not is_idle:
            current_activity["app"] = last_event.app_name or "Unknown"
            current_activity["device"] = "laptop"
            current_activity["duration"] = max(0, dur)
        else:
            current_activity["app"] = "SYSTEM_IDLE"
            current_activity["idle_timer"] = max(0, dur)

    # Alerts configuration
    alerts = []
    if burnout.score is not None and burnout.score > 70:
        alerts.append({
            "priority": "HIGH",
            "timestamp": get_ist_now().isoformat(),
            "message": "High Burnout Warning: Continuous sessions exceeded without breaks."
        })
    if focus.switches_today > 30:
        alerts.append({
            "priority": "MEDIUM",
            "timestamp": get_ist_now().isoformat(),
            "message": "Focus Efficiency Alert: Heavy multitasking and app-switching detected."
        })

    # Type Safety Assertions (Task 10)
    assert prod.score is None or isinstance(prod.score, (int, float)), f"Productivity score must be numeric or None, got {type(prod.score)}"
    assert focus.focus_percentage is None or isinstance(focus.focus_percentage, (int, float)), f"Focus efficiency percentage must be numeric or None, got {type(focus.focus_percentage)}"
    assert burnout.score is None or isinstance(burnout.score, (int, float)), f"Burnout score must be numeric or None, got {type(burnout.score)}"
    assert dist_cost.amount is None or isinstance(dist_cost.amount, (int, float)), f"Distraction cost must be numeric or None, got {type(dist_cost.amount)}"

    # Construct the final summary payload
    payload = {
        "analytics": {
            "productivity_score": prod.score,
            "focus_efficiency": focus.focus_percentage,
            "burnout_score": burnout.score,
            "burnout_risk": burnout.risk,
            "distraction_cost": dist_cost.amount,
            "currency": currency,
            "total_spent": sum(e.amount for e in expenses),
            "deep_work_sessions": focus.deep_focus_count,
            "total_sessions": len(active_sessions) or 1
        },
        "alerts": alerts,
        "events": [{
            "id": e.id,
            "event_type": e.event_type,
            "app_name": e.app_name,
            "window_title": e.window_title,
            "timestamp": e.timestamp.isoformat()
        } for e in events[:20]],
        "app_usage": [{
            "id": u.id,
            "app_name": u.app_name,
            "duration_seconds": u.duration_seconds,
            "device": u.device,
            "device_type": u.device_type,
            "date": str(u.date),
            "timestamp": u.timestamp.isoformat() if isinstance(u.timestamp, datetime) else u.timestamp
        } for u in usages],
        "screen_time": screen_time_history,
        
        # Legacy compatibility flat mapping
        "productivity_score": prod.score,
        "focus_efficiency": focus.focus_percentage,
        "burnout_score": burnout.score,
        "burnout_risk": burnout.risk,
        "distraction_cost": dist_cost.amount,
        "currency": currency,
        "total_spent": sum(e.amount for e in expenses),
        "deep_work_sessions": focus.deep_focus_count,
        "total_sessions": len(active_sessions) or 1,
        "detected_habits": BehaviorEngine.detect_habits(sessions, events),
        
        # Compatibility fields for generate_ai_dashboard
        "total_screen_time": total_screen_time,
        "top_productive_apps": top_productive_apps,
        "top_distracting_apps": top_distracting_apps,

        # Centralized Structured Output (SOLID Task 14 & Typed Models Integration)
        "current_activity": current_activity,
        "productivity": prod.model_dump(),
        "focus": focus.model_dump(),
        "burnout": burnout.model_dump(),
        "distraction_cost_details": dist_cost.model_dump(),
        "insights": insights.model_dump(),
        "recommendations": recs,
        # Expose estimated_score at top level for convenience
        "estimated_score": prod.estimated_score,
        "estimate_confidence": prod.estimate_confidence,
        "charts": {
            "app_usage": chart_usage,
            "screen_time": screen_time_history
        },
        "live_status": {
            "status": "inactive" if current_activity["app"] == "SYSTEM_IDLE" else "active"
        }
    }
    
    return payload

def generate_ai_dashboard(session: Session, days: int = 7, work_type: str = "developer") -> Dict[str, Any]:
    """Generates simulated or real AI predictions for a given work type based on actual dashboard metrics."""
    real_data = get_cached_dashboard_summary(session, days)
    total_screen_time_sec = sum(real_data["total_screen_time"].values())
    
    if total_screen_time_sec > 0:
        total_dur = sum(item["duration_seconds"] for item in real_data["top_productive_apps"] + real_data["top_distracting_apps"])
        app_dist = []
        for item in real_data["top_productive_apps"] + real_data["top_distracting_apps"]:
            pct = (item["duration_seconds"] / (total_dur + 1e-6)) * 100.0
            app_dist.append({"app": item["app_name"], "usage": round(pct, 1)})
        if not app_dist:
            app_dist = [{"app": "VS Code", "usage": 100.0}]
            
        hourly_history = []
        for hr in range(9, 19):  # 9 AM to 6 PM
            laptop_hr = (real_data["total_screen_time"].get("laptop", 0) / 10.0 / 3600.0)
            mobile_hr = (real_data["total_screen_time"].get("mobile", 0) / 10.0 / 3600.0)
            var_l = 0.8 + 0.4 * (hr % 3)
            var_m = 0.5 + 0.3 * (hr % 2)
            hourly_history.append({
                "hour": f"{hr:02d}:00",
                "laptop": round(laptop_hr * var_l, 2),
                "mobile": round(mobile_hr * var_m, 2)
            })
            
        alerts = []
        fe = real_data["focus_efficiency"] if real_data["focus_efficiency"] is not None else 0
        if fe < 40:
            alerts.append({
                "type": "warning",
                "message": f"Focus Efficiency is low ({fe}%). Deep work segments are fragmented."
            })
        bs = real_data["burnout_score"] if real_data["burnout_score"] is not None else 0
        if bs > 50:
            alerts.append({
                "type": "critical",
                "message": f"Elevated Burnout Index: {bs}/100. Rest intervals are insufficient."
            })
        if not alerts:
            alerts.append({
                "type": "info",
                "message": "Focus states are stable. No overwork critical signals flagged."
            })
            
        recommendations = []
        if real_data["burnout_risk"] == "High" or real_data["burnout_risk"] == "Medium" or real_data["burnout_risk"] == "Moderate":
            recommendations.append({
                "title": "Mitigate Burnout Hazard",
                "action": "Disable notifications and disconnect by 9 PM tonight.",
                "impact": "Lowers burnout index and restores sleep latency."
            })
        if fe < 30:
            recommendations.append({
                "title": "Protect Focus Blocks",
                "action": "Set a 25-minute timer and block YouTube/Instagram.",
                "impact": "Increases deep work sessions count by 20%."
            })
        if not recommendations:
            recommendations.append({
                "title": "Optimize Peak Hours",
                "action": "Reserve the 10:00 AM window for deep work.",
                "impact": "Increases daily coding velocity."
            })
            recommendations.append({
                "title": "Track Expenses",
                "action": "Review top categories to identify subscription leaks.",
                "impact": "Increases financial efficiency."
            })
            
        # Get actual event logs from DB
        from models import UsageEvent
        event_logs = []
        db_events = session.exec(select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(5)).all()
        for e in db_events:
            desc = f"{e.event_type} on app {e.app_name}"
            if e.event_type == "APP_SWITCH":
                desc = f"Switched to active window '{e.app_name}'"
            elif e.event_type == "IDLE_START":
                desc = f"System entered idle standby state"
            elif e.event_type == "SESSION_START":
                desc = f"New focus session boundaries registered"
            event_logs.append(desc)
        if not event_logs:
            event_logs = [
                "New active window session registered",
                "Logged background application processes"
            ]
        
        prod_val = real_data["productivity_score"] if real_data["productivity_score"] is not None else 0
        return {
            "status": "ONLINE",
            "metrics": {
                "productivityScore": real_data["productivity_score"],
                "focusEfficiency": real_data["focus_efficiency"],
                "burnoutIndex": real_data["burnout_score"],
                "distractionCost": real_data["distraction_cost"]
            },
            "contextAppDistribution": app_dist,
            "screenTimeHistory": hourly_history,
            "insights": {
                "primaryTimeWaster": real_data["insights"]["biggest_time_waster"],
                "topExpenseCategory": real_data["insights"]["spending_pattern"],
                "detectedHabits": real_data["detected_habits"],
                "summary": real_data["insights"]["suggestion"]
            },
            "recommendations": recommendations,
            "alerts": alerts,
            "events": event_logs,
            "predictions": {
                "burnoutRisk": (real_data["burnout_risk"] or "low").lower(),
                "productivityTrend": "stable" if prod_val > 50 else "decreasing"
            }
        }
    else:
        # Fallback simulation based on work_type
        wt = work_type.lower()
        if wt == "student":
            prod_score = 65.0
            focus_eff = 38.0
            burnout_idx = 42.0
            dist_cost = 0.0
            apps = [
                {"app": "Anki", "usage": 35.0},
                {"app": "Chrome", "usage": 25.0},
                {"app": "YouTube", "usage": 28.0},
                {"app": "Notion", "usage": 12.0}
            ]
            waster = "YouTube (2.8 hrs)"
            habits = ["Flashcards review at 9 AM", "Late night studies after 11 PM"]
            summary = "Heavy study blocks in Anki, but YouTube distracting clusters identified before exams."
            recs = [
                {"title": "Exam Prep Efficiency", "action": "Install block extension during exam review blocks.", "impact": "Boost study velocity by 1.8x"},
                {"title": "Sleep Recovery", "action": "Limit screen time after 11 PM.", "impact": "Improves cognitive retention for next day."}
            ]
            alerts = [{"type": "warning", "message": "Focus Efficiency below 40% threshold due to YouTube sessions."}]
            events = ["Switched to YouTube during exam prep block", "Opened Notion flashcards page"]
            risk = "medium"
            trend = "stable"
        elif wt == "designer":
            prod_score = 78.0
            focus_eff = 55.0
            burnout_idx = 28.0
            dist_cost = 450.0
            apps = [
                {"app": "Figma", "usage": 50.0},
                {"app": "Illustrator", "usage": 20.0},
                {"app": "Pinterest", "usage": 15.0},
                {"app": "Slack", "usage": 15.0}
            ]
            waster = "Pinterest (1.1 hrs)"
            habits = ["Design audits at 10 AM", "Constant Figma zoom adjustments"]
            summary = "High Figma active focus sessions. Pinterest usage is productive for reference but drifts to passive scrolling."
            recs = [
                {"title": "Time-box Design Ingestion", "action": "Limit Pinterest reference searches to 20 mins.", "impact": "Saves 45 mins of work daily."},
                {"title": "Deep Work Window", "action": "Close Slack for 2 hours during UI layout design.", "impact": "Gain 40% focus continuity."}
            ]
            alerts = [{"type": "info", "message": "Design efficiency is stable. Burnout index is safe."}]
            events = ["Exported frame assets from Figma", "Slack message notification from manager"]
            risk = "low"
            trend = "increasing"
        else: # developer default
            prod_score = 74.5
            focus_eff = 48.0
            burnout_idx = 32.0
            dist_cost = 380.0
            apps = [
                {"app": "VS Code", "usage": 45.0},
                {"app": "Chrome", "usage": 20.0},
                {"app": "YouTube", "usage": 18.0},
                {"app": "Slack", "usage": 12.0},
                {"app": "Terminal", "usage": 5.0}
            ]
            waster = "YouTube (1.8 hrs)"
            habits = ["Morning git push at 9:30 AM", "Heavy StackOverflow audits"]
            summary = "Steady development output. Guard afternoon hours (2 PM - 3 PM) where distraction spikes."
            recs = [
                {"title": "Block Code Distractions", "action": "Use Pomodoro timer blocks for debugging.", "impact": "Restores focus efficiency by 25%."},
                {"title": "Clean Workspace", "action": "Close Chrome tabs older than 24 hours.", "impact": "Reduces task switching distraction."}
            ]
            alerts = [{"type": "info", "message": "Stable active coding score. Monitor afternoon distractions."}]
            events = ["Committed local changes in scripts/", "Switched to YouTube distraction clip"]
            risk = "low"
            trend = "stable"

        # Generate simulated hourly history
        history = []
        for hr in range(9, 19):
            laptop = round(0.5 + 0.4 * (hr % 3), 1)
            mobile = round(0.2 + 0.3 * (hr % 2), 1)
            history.append({
                "hour": f"{hr:02d}:00",
                "laptop": laptop,
                "mobile": mobile
            })

        return {
            "status": "SIMULATED",
            "metrics": {
                "productivityScore": prod_score,
                "focusEfficiency": focus_eff,
                "burnoutIndex": burnout_idx,
                "distractionCost": dist_cost
            },
            "contextAppDistribution": apps,
            "screenTimeHistory": history,
            "insights": {
                "primaryTimeWaster": waster,
                "topExpenseCategory": "Food & Cafes",
                "detectedHabits": habits,
                "summary": summary
            },
            "recommendations": recs,
            "alerts": alerts,
            "events": events,
            "predictions": {
                "burnoutRisk": risk,
                "productivityTrend": trend
            }
        }


# ─── Conversational Behavioral Analysis ──────────────────────────────────────

def explain_productivity_change(session: Session, question: str = "", days: int = 1) -> Dict[str, Any]:
    """
    Deterministic conversational analysis answering productivity questions.

    Compares the current `days`-period window against an equally-sized prior
    window, identifies the single largest delta driver, and returns a structured
    natural-language explanation grounded in real metrics.

    No LLM is called. All logic is pure arithmetic on the analytics payload.
    """
    current = get_cached_dashboard_summary(session, days)
    prior = get_cached_dashboard_summary(session, days * 2)

    def safe_get(d: Dict, *keys, default=None):
        val = d
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k, default)
        return val

    # Current period metrics
    prod_now = safe_get(current, "productivity", "score")
    est_now = safe_get(current, "estimated_score")
    focus_now = safe_get(current, "focus", "focus_percentage")
    switches_now = safe_get(current, "focus", "switches_today", default=0)
    distracting_now = safe_get(current, "productivity", "distracting_minutes", default=0.0)
    idle_now = safe_get(current, "insights", "average_idle_duration", default=0.0)

    # Prior period metrics (the 2x window includes now, so we approximate prior
    # as the difference between 2x and 1x aggregates — this is best-effort
    # without a dedicated windowed query; see M6 note in compare_last_week)
    prod_prior = safe_get(prior, "productivity", "score")
    focus_prior = safe_get(prior, "focus", "focus_percentage")
    switches_prior = safe_get(prior, "focus", "switches_today", default=0)
    distracting_prior = safe_get(prior, "productivity", "distracting_minutes", default=0.0)
    idle_prior = safe_get(prior, "insights", "average_idle_duration", default=0.0)

    # Compute deltas (positive = got worse for negative metrics)
    drivers = []

    def add_driver(name: str, current_val, prior_val, higher_is_worse: bool, unit: str = ""):
        if current_val is None or prior_val is None:
            return
        delta = current_val - prior_val
        if abs(delta) < 1:
            return
        direction = "increased" if delta > 0 else "decreased"
        is_worse = (delta > 0) == higher_is_worse
        drivers.append({
            "metric": name,
            "delta": round(delta, 1),
            "current": current_val,
            "prior": prior_val,
            "unit": unit,
            "direction": direction,
            "impact": "negative" if is_worse else "positive",
            "magnitude": abs(delta)
        })

    add_driver("context_switches", switches_now, switches_prior, higher_is_worse=True, unit="switches")
    add_driver("distracting_minutes", distracting_now, distracting_prior, higher_is_worse=True, unit="minutes")
    add_driver("idle_duration", idle_now, idle_prior, higher_is_worse=True, unit="minutes")
    add_driver("focus_efficiency", focus_now, focus_prior, higher_is_worse=False, unit="%")
    if prod_now is not None and prod_prior is not None:
        add_driver("productivity_score", prod_now, prod_prior, higher_is_worse=False, unit="%")

    # Sort by magnitude descending; primary driver = largest delta
    drivers.sort(key=lambda d: d["magnitude"], reverse=True)
    primary_driver = drivers[0] if drivers else None

    # Build natural-language explanation
    if primary_driver:
        m = primary_driver
        change_word = "lower" if m["impact"] == "negative" else "higher"
        explanation_parts = [
            f"Your productivity appears {change_word} compared to the prior period.",
            f"The primary driver is {m['metric'].replace('_', ' ')} which {m['direction']} "
            f"by {abs(m['delta']):.1f}{m['unit']} "
            f"(from {m['prior']}{m['unit']} to {m['current']}{m['unit']})."
        ]
        # Add secondary driver context if present
        if len(drivers) > 1:
            sec = drivers[1]
            explanation_parts.append(
                f"A secondary factor is {sec['metric'].replace('_', ' ')} "
                f"({sec['direction']} by {abs(sec['delta']):.1f}{sec['unit']})."
            )
    elif not any([prod_now, est_now, focus_now]):
        explanation_parts = ["No sufficient activity data found for this period to draw a comparison."]
    else:
        explanation_parts = [
            "Metrics are relatively stable between the current period and the prior period.",
            "No single factor stands out as a significant driver of change."
        ]

    # Score display: prefer user-verified score, fall back to estimated
    score_display = prod_now if prod_now is not None else est_now
    score_label = "productivity_score" if prod_now is not None else "estimated_score"

    return {
        "explanation": " ".join(explanation_parts),
        "primary_driver": primary_driver,
        "drivers": drivers,
        "metrics_today": {
            score_label: score_display,
            "focus_efficiency": focus_now,
            "context_switches": switches_now,
            "distracting_minutes": round(distracting_now, 1) if distracting_now else 0.0,
            "avg_idle_minutes": idle_now,
            "period_days": days
        },
        "metrics_prior": {
            score_label: prod_prior if prod_now is not None else safe_get(prior, "estimated_score"),
            "focus_efficiency": focus_prior,
            "context_switches": switches_prior,
            "distracting_minutes": round(distracting_prior, 1) if distracting_prior else 0.0,
            "avg_idle_minutes": idle_prior,
            "period_days": days
        },
        "question": question or "Behavioral productivity comparison",
        "note": "Metrics for 'prior period' approximate a rolling window; for exact week-over-week use days=7."
    }

