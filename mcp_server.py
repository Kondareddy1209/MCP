"""
mcp_server.py — it'syou MCP (Model Context Protocol) Server
Exposes 25 tools, 6 resources, and 6 prompts utilizing the centralized analytics service.
"""
from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, select
from datetime import date, datetime, timedelta
import json
import os
import requests
from typing import List, Dict, Any

from db import engine
from models import Expense, DailyScreenTime, AppClassification, UsageEvent, AppUsage
import crud
from services.analytics import get_cached_dashboard_summary, get_ist_now, auto_classify, explain_productivity_change as _explain_change

mcp = FastMCP("it'syou")

API_BASE_URL = "http://localhost:8000/api"

# Helper for GET/POST requests to local FastAPI (decoupling daemon controls)
def _request_api(method: str, path: str, data: dict = None) -> Dict[str, Any]:
    url = f"{API_BASE_URL}/{path.lstrip('/')}"
    try:
        if method.upper() == "POST":
            r = requests.post(url, json=data, timeout=3)
        else:
            r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return r.json()
        return {"status": "error", "message": f"Server status: {r.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Connection error: {e}"}


# ─── MCP TOOLS ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_dashboard_metrics(days: int = 7) -> str:
    """Gets the complete dashboard analytics metrics for the last N days."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        return json.dumps(data.get("analytics", {}), indent=2)

@mcp.tool()
def get_current_activity() -> str:
    """Gets the currently active application, device, and active focus durations."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, 1)
        return json.dumps(data.get("current_activity", {}), indent=2)

@mcp.tool()
def get_productivity_score(days: int = 7) -> str:
    """Calculates your productivity score and active/neutral/distracting durations.
    Returns both the verified score (null if no user classifications configured) and
    an estimated score computed from auto_classify() regex heuristics."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        prod = data.get("productivity", {})
        score = prod.get('score')
        est = data.get('estimated_score')
        if score is not None:
            score_str = f"{score}% (verified)"
        elif est is not None:
            score_str = f"~{est}% (estimated, auto-classified)"
        else:
            score_str = "No data"
        return (f"Productivity Score: {score_str} | "
                f"Productive: {prod.get('productive_minutes')}m | "
                f"Distracting: {prod.get('distracting_minutes')}m")

@mcp.tool()
def get_focus_efficiency(days: int = 7) -> str:
    """Calculates focus efficiency percentage, average sessions, and context switches."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        focus = data.get("focus", {})
        return f"Focus Efficiency: {focus.get('focus_percentage')}% | Longest Focus: {focus.get('longest_session')}m | Deep Focus Sessions: {focus.get('deep_focus_count')} | Context Switches: {focus.get('switches_today')}"

@mcp.tool()
def get_burnout_index(days: int = 7) -> str:
    """Calculates your behavioral burnout index (0-100) and risk level."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        burnout = data.get("burnout", {})
        return f"Burnout Index: {burnout.get('score')}/100 | Risk Level: {burnout.get('risk')}"

@mcp.tool()
def get_distraction_cost(days: int = 7) -> str:
    """Calculates the opportunity cost incurred from distractions based on user rate."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        cost = data.get("distraction_cost_details", {})
        return f"Distraction Opportunity Cost: {cost.get('currency')} {cost.get('amount') if cost.get('amount') is not None else 'Unknown'}"

@mcp.tool()
def get_behavioral_insights(days: int = 7) -> str:
    """Generates detailed behavioral insights (most used apps, peak productive hours, switch counts)."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        return json.dumps(data.get("insights", {}), indent=2)

@mcp.tool()
def get_recent_events(limit: int = 20) -> str:
    """Retrieves the list of recent focus, blur, and idle events from the database."""
    with Session(engine) as session:
        events = session.exec(select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(limit)).all()
        result = [{
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "app_name": e.app_name,
            "window_title": e.window_title
        } for e in events]
        return json.dumps(result, indent=2)

@mcp.tool()
def get_screen_time_history(days: int = 7) -> str:
    """Retrieves screen time records (hourly buckets for Today, daily records for multi-day)."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        return json.dumps(data.get("screen_time", []), indent=2)

@mcp.tool()
def get_app_distribution(days: int = 7) -> str:
    """Retrieves total duration statistics grouped by application name."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        return json.dumps(data.get("app_usage", []), indent=2)

@mcp.tool()
def get_daily_summary() -> str:
    """Gets a comprehensive report of today's behavioral insights and productivity metrics."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, 1)
        return json.dumps(data, indent=2)

@mcp.tool()
def get_weekly_summary() -> str:
    """Gets a comprehensive report of focus metrics and burnout index for the last 7 days."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, 7)
        return json.dumps(data, indent=2)

@mcp.tool()
def get_monthly_summary() -> str:
    """Gets a comprehensive report of focus metrics and burnout index for the last 30 days."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, 30)
        return json.dumps(data, indent=2)

@mcp.tool()
def search_usage(app_name: str) -> str:
    """Searches application usage logs for a specific application name."""
    with Session(engine) as session:
        usages = session.exec(select(AppUsage).where(AppUsage.app_name.like(f"%{app_name}%")).limit(30)).all()
        result = [{
            "app_name": u.app_name,
            "duration_seconds": u.duration_seconds,
            "device": u.device,
            "timestamp": u.timestamp.isoformat() if u.timestamp else None
        } for u in usages]
        return json.dumps(result, indent=2)

@mcp.tool()
def search_sessions(session_id: str) -> str:
    """Retrieves all application usage logs associated with a given tracker session ID."""
    with Session(engine) as session:
        usages = session.exec(select(AppUsage).where(AppUsage.session_id == session_id)).all()
        result = [{
            "app_name": u.app_name,
            "duration_seconds": u.duration_seconds,
            "timestamp": u.timestamp.isoformat() if u.timestamp else None,
            "activity_score": u.activity_score
        } for u in usages]
        return json.dumps(result, indent=2)

@mcp.tool()
def find_longest_focus_session(days: int = 7) -> str:
    """Finds the longest uninterrupted application usage session in the N-day window."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        insights = data.get("insights", {})
        return f"Longest Session: {insights.get('longest_session')}"

@mcp.tool()
def list_devices() -> str:
    """Lists all active device types and names ingested by the dashboard."""
    with Session(engine) as session:
        devices = session.exec(select(AppUsage.device).distinct()).all()
        return json.dumps({"devices": [d for d in devices if d]}, indent=2)

@mcp.tool()
def get_last_active_app() -> str:
    """Queries the backend for the last active foreground app details."""
    res = _request_api("GET", "last-active-app")
    return json.dumps(res, indent=2)

@mcp.tool()
def classify_application(app_name: str, classification: str) -> str:
    """Saves or updates application classification ('productive', 'distracting', or 'neutral')."""
    class_clean = classification.lower().strip()
    if class_clean not in ["productive", "distracting", "neutral"]:
        return "Error: classification must be 'productive', 'distracting', or 'neutral'."
    ac = AppClassification(app_name=app_name, classification=class_clean)
    with Session(engine) as session:
        crud.upsert_classification(session, ac)
        # invalidate cache
        from services.analytics import invalidate_analytics_cache
        invalidate_analytics_cache()
        return f"Application '{app_name}' successfully classified as '{class_clean}'."

@mcp.tool()
def start_tracker() -> str:
    """Commands the desktop tracker daemon to start/resume key/mouse activity checks."""
    res = _request_api("POST", "tracker/start")
    return json.dumps(res, indent=2)

@mcp.tool()
def stop_tracker() -> str:
    """Commands the desktop tracker daemon to stop key/mouse hook listeners."""
    res = _request_api("POST", "tracker/stop")
    return json.dumps(res, indent=2)

@mcp.tool()
def pause_tracker() -> str:
    """Commands the desktop tracker daemon to temporarily pause monitoring active apps."""
    res = _request_api("POST", "tracker/pause")
    return json.dumps(res, indent=2)

@mcp.tool()
def resume_tracker() -> str:
    """Commands the desktop tracker daemon to resume app monitoring from a paused state."""
    res = _request_api("POST", "tracker/resume")
    return json.dumps(res, indent=2)

@mcp.tool()
def health_check() -> str:
    """Runs a diagnostics health check of the platform, REST api, and SQLite connection."""
    res = _request_api("GET", "tracker/status")
    db_ok = False
    try:
        with Session(engine) as session:
            session.exec(select(Expense).limit(1)).all()
            db_ok = True
    except Exception:
        pass
    return json.dumps({
        "status": "ONLINE" if db_ok else "OFFLINE",
        "database_connected": db_ok,
        "tracker_status": res
    }, indent=2)


# ─── RICH BEHAVIORAL TOOLS (Phase 7) ───────────────────────────────────────

@mcp.tool()
def analyze_productivity(days: int = 7) -> str:
    """Provides a detailed behavioral productivity analysis.
    Returns productivity_score (null if no user classifications) alongside
    estimated_score (auto_classify heuristic) and estimate_confidence."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        prod = data.get("productivity", {})
        res = {
            "productivity_score": prod.get("score"),
            "estimated_score": data.get("estimated_score"),
            "estimate_confidence": data.get("estimate_confidence"),
            "productive_minutes": prod.get("productive_minutes"),
            "neutral_minutes": prod.get("neutral_minutes"),
            "distracting_minutes": prod.get("distracting_minutes"),
            "range_days": days
        }
        return json.dumps(res, indent=2)

@mcp.tool()
def analyze_focus(days: int = 7) -> str:
    """Calculates focus efficiency, average session duration, context switches and deep focus sessions."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        focus = data.get("focus", {})
        res = {
            "focus_efficiency": focus.get("focus_percentage"),
            "average_session_minutes": focus.get("average_session"),
            "longest_session_minutes": focus.get("longest_session"),
            "deep_focus_count": focus.get("deep_focus_count"),
            "context_switches": focus.get("switches_today"),
            "range_days": days
        }
        return json.dumps(res, indent=2)

@mcp.tool()
def detect_habits(days: int = 7) -> str:
    """Identifies routine patterns, peak focus hours, and primary apps used."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        insights = data.get("insights", {})
        res = {
            "detected_habits": data.get("detected_habits", []),
            "most_used_app": insights.get("most_used_app"),
            "peak_productive_hour": insights.get("peak_productive_hour"),
            "peak_distraction_hour": insights.get("peak_distraction_hour"),
            "range_days": days
        }
        return json.dumps(res, indent=2)

@mcp.tool()
def detect_distractions(days: int = 7) -> str:
    """Pinpoints distracting applications, cost rate leaks, and biggest time wasters."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        insights = data.get("insights", {})
        cost = data.get("distraction_cost_details", {})
        res = {
            "most_distracting_app": insights.get("most_distracting_app"),
            "biggest_time_waster": insights.get("biggest_time_waster"),
            "distraction_cost": cost.get("amount"),
            "currency": cost.get("currency", "INR"),
            "distracting_minutes": data.get("productivity", {}).get("distracting_minutes", 0.0),
            "range_days": days
        }
        return json.dumps(res, indent=2)

@mcp.tool()
def predict_burnout(days: int = 7) -> str:
    """Predicts user fatigue, overwork hazard, and burnout risk index."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        burnout = data.get("burnout", {})
        res = {
            "burnout_score": burnout.get("score"),
            "burnout_risk": burnout.get("risk"),
            "warnings_flagged": burnout.get("warnings", []),
            "range_days": days
        }
        return json.dumps(res, indent=2)

@mcp.tool()
def compare_last_week() -> str:
    """Compares the current 7-day window against the prior 7-day window (genuinely isolated, not folded)."""
    from datetime import date, timedelta
    from sqlmodel import select
    from models import AppUsage, UsageEvent, AppClassification
    from services.session_engine import SessionEngine
    from services.behavior_engine import BehaviorEngine
    import json as _json

    today = get_ist_now().date()
    # Current window: today-6 .. today
    current_start = today - timedelta(days=6)
    # Prior window: today-13 .. today-7
    prior_start = today - timedelta(days=13)
    prior_end = today - timedelta(days=7)

    def _compute_window(start: date, end: date):
        """Compute summary for an exact date window [start, end] inclusive."""
        with Session(engine) as s:
            from datetime import datetime, time as dtime
            start_ts = datetime.combine(start, dtime.min)
            end_ts = datetime.combine(end, dtime(23, 59, 59))
            usages = s.exec(
                select(AppUsage).where(AppUsage.date >= start, AppUsage.date <= end)
            ).all()
            events = s.exec(
                select(UsageEvent).where(
                    UsageEvent.timestamp >= start_ts,
                    UsageEvent.timestamp <= end_ts
                ).order_by(UsageEvent.timestamp.desc())
            ).all()
            classifications = {c.app_name.lower(): c.classification for c in s.exec(select(AppClassification)).all()}

        sessions = SessionEngine.reconstruct_sessions(usages, events)
        prod = BehaviorEngine.analyze_productivity(sessions, classifications)
        focus = BehaviorEngine.analyze_focus(sessions, events)
        burnout = BehaviorEngine.analyze_burnout(sessions)
        dist_cost = BehaviorEngine.analyze_distraction_cost(sessions, classifications, 200)
        return {
            "productivity_score": prod.score,
            "estimated_score": prod.estimated_score,
            "burnout_score": burnout.score,
            "focus_efficiency": focus.focus_percentage,
            "context_switches": focus.switches_today,
            "distracting_minutes": prod.distracting_minutes,
        }

    this_week = _compute_window(current_start, today)
    prior_week = _compute_window(prior_start, prior_end)

    res = {
        "this_week": {**this_week, "window": f"{current_start} to {today}"},
        "prior_week": {**prior_week, "window": f"{prior_start} to {prior_end}"},
        "comparison_notes": (
            "Windows are genuinely isolated (7-day each). "
            "A lower burnout score and higher productivity score indicates positive focus adjustments."
        )
    }
    return _json.dumps(res, indent=2)

@mcp.tool()
def generate_behavior_report(days: int = 7) -> str:
    """Generates a complete markdown behavioral intelligence and audit report."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        prod = data.get("productivity", {})
        focus = data.get("focus", {})
        burnout = data.get("burnout", {})
        insights = data.get("insights", {})
        
        report = f"""# Behavioral Telemetry & Attention Audit Report (Last {days} Days)

## 1. Executive Summary
- **Productivity Score**: {prod.get('score') if prod.get('score') is not None else 'Unknown'}%
- **Focus Efficiency**: {focus.get('focus_percentage') if focus.get('focus_percentage') is not None else 'Unknown'}%
- **Burnout Risk Index**: {burnout.get('score') if burnout.get('score') is not None else 'Unknown'}/100 ({burnout.get('risk') or 'Unknown'} Risk)

## 2. Attention Allocation
- **Productive Time**: {prod.get('productive_minutes', 0.0)} mins
- **Neutral Time**: {prod.get('neutral_minutes', 0.0)} mins
- **Distracting Time**: {prod.get('distracting_minutes', 0.0)} mins

## 3. Work Habits & Insights
- **Most Used Application**: {insights.get('most_used_app') or 'No data'}
- **Biggest Distraction Source**: {insights.get('biggest_time_waster') or 'None'}
- **Peak Focus Hour**: {insights.get('peak_productive_hour') or 'No data'}
- **Average Focus Session Length**: {insights.get('average_session_duration') or '0.0'} mins

## 4. Coaching Recommendations
"""
        for r in data.get("recommendations", []):
            report += f"- {r}\n"
            
        return report

@mcp.tool()
def recommend_improvements(days: int = 7) -> str:
    """Returns dynamic, rule-based focus improvement advice checklist based on metrics."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, days)
        return json.dumps({
            "recommendations": data.get("recommendations", []),
            "range_days": days
        }, indent=2)


@mcp.tool()
def explain_productivity_change(question: str = "Why was my productivity lower today?", days: int = 1) -> str:
    """Answers conversational behavioral questions by comparing the current period to a prior window.

    Compares productivity score, context switches, idle time, and distracting-app
    usage between the current `days` window and an equally-sized prior window.
    Returns a structured explanation with ranked drivers. Fully deterministic — no LLM.

    Args:
        question: Natural language question (e.g., 'Why was my focus worse this week?')
        days:     Size of each comparison window in days (1=today vs yesterday, 7=this week vs last week)

    Returns:
        JSON with keys: explanation, primary_driver, drivers, metrics_today, metrics_prior
    """
    with Session(engine) as session:
        result = _explain_change(session, question=question, days=days)
        return json.dumps(result, indent=2)


# ─── MCP RESOURCES ─────────────────────────────────────────────────────────

@mcp.resource("dashboard://current")
def get_current_dashboard_resource() -> str:
    """Exposes current today's dashboard aggregate summary as a JSON resource."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, 1)
        return json.dumps(data, indent=2)

@mcp.resource("metrics://today")
def get_today_metrics_resource() -> str:
    """Exposes today's productivity, burnout, and distraction cost metrics as a JSON resource."""
    with Session(engine) as session:
        data = get_cached_dashboard_summary(session, 1)
        metrics = {
            "productivity": data.get("productivity", {}),
            "focus": data.get("focus", {}),
            "burnout": data.get("burnout", {}),
            "distraction_cost": data.get("distraction_cost_details", {})
        }
        return json.dumps(metrics, indent=2)

@mcp.resource("events://recent")
def get_recent_events_resource() -> str:
    """Exposes the last 20 usage focus, blur, and idle events logged into SQLite."""
    with Session(engine) as session:
        events = session.exec(select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(20)).all()
        res = [{
            "timestamp": e.timestamp.isoformat(),
            "event_type": e.event_type,
            "app_name": e.app_name,
            "window_title": e.window_title
        } for e in events]
        return json.dumps(res, indent=2)

@mcp.resource("devices://status")
def get_device_status_resource() -> str:
    """Exposes current active device name and tracker session info."""
    res = _request_api("GET", "tracker/status")
    return json.dumps(res, indent=2)

@mcp.resource("cache://analytics")
def get_analytics_cache_resource() -> str:
    """Exposes current in-memory dashboard cache keys."""
    from services.analytics import _DASHBOARD_CACHE
    keys = [str(k) for k in _DASHBOARD_CACHE.keys()]
    return json.dumps({"cached_keys": keys, "cache_size": len(_DASHBOARD_CACHE)}, indent=2)

@mcp.resource("classifications://all")
def get_classifications_resource() -> str:
    """Exposes all saved custom application classifications."""
    with Session(engine) as session:
        classes = session.exec(select(AppClassification)).all()
        res = {c.app_name: c.classification for c in classes}
        return json.dumps(res, indent=2)


# ─── MCP PROMPTS ───────────────────────────────────────────────────────────

@mcp.prompt()
def get_prompt_most_distracted() -> str:
    """Prompt template for querying biggest distraction today."""
    return "What distracted me the most today?"

@mcp.prompt()
def get_prompt_summarize_productivity() -> str:
    """Prompt template for summarizing today's productivity score."""
    return "Summarize today's productivity."

@mcp.prompt()
def get_prompt_longest_focus() -> str:
    """Prompt template for locating the longest uninterrupted session today."""
    return "Show my longest focus session."

@mcp.prompt()
def get_prompt_weekly_report() -> str:
    """Prompt template for requesting a weekly behavioral telemetry audit report."""
    return "Generate a weekly behavioral report."

@mcp.prompt()
def get_prompt_most_time_consuming() -> str:
    """Prompt template for identifying top applications by duration."""
    return "Which applications consumed the most time?"

@mcp.prompt()
def get_prompt_app_switches() -> str:
    """Prompt template for auditing context app switching frequency."""
    return "How many times did I switch applications?"


if __name__ == "__main__":
    mcp.run()
