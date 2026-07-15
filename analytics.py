from sqlmodel import Session, select
from datetime import date, timedelta, datetime
import json
import os
from typing import List, Dict, Any

from models import Expense, AppUsage, DailyScreenTime, AppClassification, ProductivityMetricsCache
from crud import get_classifications
from classification import auto_classify

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> Dict[str, Any]:
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"hourly_rate": 200, "currency": "INR"}

def calculate_focus_sessions(usages: List[AppUsage]) -> List[List[AppUsage]]:
    """Groups chronological usages into sessions with gap threshold of 5 minutes (300 seconds)."""
    usages_sorted = sorted(usages, key=lambda u: u.timestamp)
    sessions = []
    current_session = []
    
    for usage in usages_sorted:
        if not current_session:
            current_session.append(usage)
        else:
            last = current_session[-1]
            last_end = last.timestamp + timedelta(seconds=last.duration_seconds)
            gap = (usage.timestamp - last_end).total_seconds()
            
            if gap <= 300:  # 5 minutes gap
                current_session.append(usage)
            else:
                sessions.append(current_session)
                current_session = [usage]
                
    if current_session:
        sessions.append(current_session)
    return sessions

def is_deep_work_session(session: List[AppUsage]) -> bool:
    """A session is deep work if it lasts >= 15 mins (900s), is >= 70% productive, and has low distraction/idle ratios."""
    total_duration = sum(u.duration_seconds for u in session)
    if total_duration == 0:
        return False
        
    productive_duration = sum(u.duration_seconds for u in session if auto_classify(u.app_name) == "productive")
    distracting_duration = sum(u.duration_seconds for u in session if auto_classify(u.app_name) == "distracting")
    idle_duration = sum(u.duration_seconds for u in session if getattr(u, "idle_flag", False))
    
    return (
        total_duration >= 900 and 
        productive_duration >= 0.7 * total_duration and 
        distracting_duration <= 0.15 * total_duration and
        idle_duration <= 0.15 * total_duration
    )


def calculate_analytics(session: Session, days: int = 7) -> Dict[str, Any]:
    config = load_config()
    hourly_rate = config.get("hourly_rate", 200)
    currency = config.get("currency", "INR")
    
    if days == 1:
        start_date = date.today()
    else:
        start_date = date.today() - timedelta(days=days)

    
    # 1. Fetch Expenses
    expense_stmt = select(Expense).where(Expense.date >= start_date)
    expenses = session.exec(expense_stmt).all()
    
    expense_summary = {}
    total_spent = 0.0
    for exp in expenses:
        expense_summary[exp.category] = expense_summary.get(exp.category, 0.0) + exp.amount
        total_spent += exp.amount

    # 2. Fetch App Usage
    usage_stmt = select(AppUsage).where(AppUsage.date >= start_date)
    usages = session.exec(usage_stmt).all()
    
    # Identify sessions
    sessions = calculate_focus_sessions(usages)
    
    deep_work_seconds = 0
    productive_seconds = 0
    distraction_seconds = 0
    neutral_seconds = 0
    intentional_breaks_seconds = 0
    waste_seconds = 0
    
    # Map app durations for ranking list
    app_durations = {}
    
    # Identify deep work sessions and calculate durations
    deep_work_session_indexes = []
    for idx, s in enumerate(sessions):
        is_dw = is_deep_work_session(s)
        if is_dw:
            deep_work_session_indexes.append(idx)
            
        for u in s:
            app_name = u.app_name
            dur = u.duration_seconds
            app_durations[app_name] = app_durations.get(app_name, 0) + dur
            
            classification = auto_classify(app_name)
            is_idle = getattr(u, "idle_flag", False)
            
            if classification == "productive":
                if is_dw:
                    deep_work_seconds += dur
                else:
                    productive_seconds += dur
            elif classification == "distracting":
                distraction_seconds += dur
                if is_idle:
                    waste_seconds += dur
                else:
                    intentional_breaks_seconds += dur
            else:
                neutral_seconds += dur

    # Top Apps lists
    top_productive_apps = []
    top_distracting_apps = []
    
    for app_name, duration in app_durations.items():
        classification = auto_classify(app_name)
        app_item = {"app_name": app_name, "duration_seconds": duration}
        if classification == "productive":
            top_productive_apps.append(app_item)
        elif classification == "distracting":
            top_distracting_apps.append(app_item)
            
    top_productive_apps = sorted(top_productive_apps, key=lambda x: x["duration_seconds"], reverse=True)[:5]
    top_distracting_apps = sorted(top_distracting_apps, key=lambda x: x["duration_seconds"], reverse=True)[:5]
    
    # Total screen time grouped by device
    screen_time_stmt = select(DailyScreenTime).where(DailyScreenTime.date >= start_date)
    screen_time_records = session.exec(screen_time_stmt).all()
    
    total_screen_time = {"mobile": 0, "laptop": 0}
    for record in screen_time_records:
        total_screen_time[record.device] = total_screen_time.get(record.device, 0) + record.total_time_seconds
        
    # Productivity Score (Advanced Formulation)
    total_seconds = deep_work_seconds + productive_seconds + distraction_seconds + neutral_seconds
    total_hours = total_seconds / 3600.0
    deep_work_hours = deep_work_seconds / 3600.0
    productive_hours = productive_seconds / 3600.0
    distraction_hours = distraction_seconds / 3600.0
    
    if total_hours > 0:
        productivity_score_raw = (deep_work_hours * 1.5 + productive_hours * 1.0 - distraction_hours * 1.2) / total_hours
        productivity_score = max(0.0, min(100.0, productivity_score_raw * 100.0))
    else:
        productivity_score = 0.0

    # Distraction Cost
    distraction_cost = distraction_hours * hourly_rate

    # Focus Efficiency
    total_sessions_count = len(sessions)
    deep_work_sessions_count = len(deep_work_session_indexes)
    focus_efficiency = (deep_work_sessions_count / total_sessions_count * 100.0) if total_sessions_count > 0 else 0.0

    # 3. Behavioral Patterns & Habit Detection
    # Peak Productivity Hour
    prod_hours = [0] * 24
    dist_hours = [0] * 24
    
    # Habit Detection (usage on distinct days)
    app_days = {} # {app: set(dates)}
    
    for u in usages:
        ts = u.timestamp
        if isinstance(ts, str):
            try:
                cleaned = ts.replace("Z", "").split(".")[0]
                ts = datetime.strptime(cleaned, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                continue
                
        hour = ts.hour
        classification = auto_classify(u.app_name)
        if classification == "productive":
            prod_hours[hour] += u.duration_seconds
        elif classification == "distracting":
            dist_hours[hour] += u.duration_seconds
            
        app_days.setdefault(u.app_name, set()).add(u.date)
        
    max_prod_duration = max(prod_hours)
    peak_productivity_hour = prod_hours.index(max_prod_duration) if max_prod_duration > 0 else -1
    
    # Distraction clusters (hours where distraction time is > 20% of total distraction)
    distraction_clusters = []
    if distraction_seconds > 0:
        for hr, dur in enumerate(dist_hours):
            if dur / distraction_seconds >= 0.20:
                distraction_clusters.append(hr)
                
    # Habit detection (apps used on >= 60% of distinct tracked days AND total duration >= 3600 seconds)
    distinct_days_count = len(set(u.date for u in usages))
    habits = []
    if distinct_days_count > 0:
        for app, dates in app_days.items():
            total_app_dur = app_durations.get(app, 0)
            if len(dates) / distinct_days_count >= 0.60 and total_app_dur >= 3600:
                habits.append(app)


    # 4. Behavioral Burnout Model
    # Late night ratio (usage between 11 PM and 4 AM / total tracked)
    late_night_seconds = 0
    for u in usages:
        ts = u.timestamp
        if isinstance(ts, str):
            try:
                cleaned = ts.replace("Z", "").split(".")[0]
                ts = datetime.strptime(cleaned, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                continue
        if ts.hour >= 23 or ts.hour < 4:
            late_night_seconds += u.duration_seconds
            
    late_night_ratio = late_night_seconds / total_seconds if total_seconds > 0 else 0.0
    
    # Overwork days ratio (screen time > 8 hours)
    daily_screen_time = {}
    for record in screen_time_records:
        daily_screen_time[record.date] = daily_screen_time.get(record.date, 0) + record.total_time_seconds
        
    overwork_days = sum(1 for sec in daily_screen_time.values() if sec > 28800)
    overwork_days_ratio = overwork_days / days if days > 0 else 0.0
    
    # Low focus ratio is 0.0 if no tracked hours exist
    low_focus_ratio = 1.0 - (deep_work_hours / total_hours) if total_hours > 0 else 0.0
    
    # Burnout score computation
    if total_seconds > 0:
        burnout_score = (late_night_ratio * 0.4 + overwork_days_ratio * 0.3 + low_focus_ratio * 0.3) * 100.0
        burnout_score = max(0.0, min(100.0, burnout_score))
        
        # Risk thresholds: only trigger High if overwork days AND late night sessions both exist
        burnout_risk = "Low"
        if burnout_score > 60 and overwork_days > 0 and late_night_seconds > 0:
            burnout_risk = "High"
        elif burnout_score > 30 and (overwork_days > 0 or late_night_seconds > 0):
            burnout_risk = "Medium"
    else:
        burnout_score = 0.0
        burnout_risk = "Low"


    # Generate insights
    insights = generate_life_insights(
        productive_time=deep_work_seconds + productive_seconds,
        distracting_time=distraction_seconds,
        app_durations=app_durations,
        total_spent=total_spent,
        expense_summary=expense_summary,
        currency=currency,
        distraction_cost=distraction_cost,
        focus_efficiency=focus_efficiency,
        peak_prod_hour=peak_productivity_hour,
        distraction_clusters=distraction_clusters,
        burnout_risk=burnout_risk,
        days=days
    )

    
    return {
        "top_productive_apps": top_productive_apps,
        "top_distracting_apps": top_distracting_apps,
        "total_screen_time": total_screen_time,
        "productivity_score": round(productivity_score, 1),
        "expense_summary": expense_summary,
        "total_spent": round(total_spent, 2),
        "distraction_cost": round(distraction_cost, 2),
        "currency": currency,
        "productive_time_seconds": deep_work_seconds + productive_seconds,
        "distracting_time_seconds": distraction_seconds,
        "neutral_time_seconds": neutral_seconds,
        "deep_work_seconds": deep_work_seconds,
        "light_productive_seconds": productive_seconds,
        "intentional_breaks_seconds": intentional_breaks_seconds,
        "waste_seconds": waste_seconds,
        "focus_efficiency": round(focus_efficiency, 1),
        "deep_work_sessions": deep_work_sessions_count,
        "total_sessions": total_sessions_count,
        "peak_productivity_hour": peak_productivity_hour,
        "distraction_clusters": distraction_clusters,
        "detected_habits": habits[:3],
        "burnout_score": round(burnout_score, 1),
        "burnout_risk": burnout_risk,
        "insights": insights
    }

def generate_life_insights(
    productive_time: int,
    distracting_time: int,
    app_durations: Dict[str, int],
    total_spent: float,
    expense_summary: Dict[str, float],
    currency: str,
    distraction_cost: float,
    focus_efficiency: float,
    peak_prod_hour: int,
    distraction_clusters: List[int],
    burnout_risk: str,
    days: int = 7
) -> Dict[str, Any]:
    
    # 1. Find biggest time wasters
    time_wasters = []
    for app_name, duration in app_durations.items():
        if auto_classify(app_name) == "distracting":
            time_wasters.append((app_name, duration))
            
    time_wasters = sorted(time_wasters, key=lambda x: x[1], reverse=True)
    
    if productive_time + distracting_time == 0:
        biggest_time_waster = "No data"
    elif time_wasters:
        app, sec = time_wasters[0]
        hours = sec / 3600.0
        biggest_time_waster = f"{app} ({round(hours, 1)} hrs)"
    else:
        biggest_time_waster = "None"

    # 2. Find spending patterns
    highest_expense_cat = "No data"
    if expense_summary and total_spent > 0:
        sorted_expenses = sorted(expense_summary.items(), key=lambda x: x[1], reverse=True)
        highest_expense_cat = f"{sorted_expenses[0][0]} ({currency} {round(sorted_expenses[0][1], 2)})"


    # 3. Formulate suggestion
    if productive_time + distracting_time == 0:
        suggestion = "No activity tracked today. Start the desktop tracker to begin auditing." if days == 1 else "No activity tracked for this range."
    else:
        suggestion = "You are maintaining a balanced lifestyle. Keep up the good work!"
        if burnout_risk == "High":
            suggestion = "🚨 Burnout Alert: Heavy overwork days and late-night usage detected. Log off early and schedule mandatory relaxation blocks!"
        elif focus_efficiency < 25.0 and productive_time > 3600:
            suggestion = f"Your Focus Efficiency is low ({round(focus_efficiency, 1)}%). You get distracted during work blocks. Try 25-minute Pomodoro sessions."
        elif distraction_clusters:
            am_pm = "AM" if distraction_clusters[0] < 12 else "PM"
            hr = distraction_clusters[0] if distraction_clusters[0] <= 12 else distraction_clusters[0] - 12
            if hr == 0:
                hr = 12
            suggestion = f"High distraction cluster identified around {hr} {am_pm}. Consider blocking entertainment apps during this window."
        elif peak_prod_hour != -1:
            am_pm = "AM" if peak_prod_hour < 12 else "PM"
            hr = peak_prod_hour if peak_prod_hour <= 12 else peak_prod_hour - 12
            if hr == 0:
                hr = 12
            suggestion = f"Your peak productivity is at {hr} {am_pm}. Guard this hour for your most demanding, critical tasks."

    return {
        "biggest_time_waster": biggest_time_waster,
        "spending_pattern": highest_expense_cat,
        "suggestion": suggestion
    }


def generate_ai_dashboard(session: Session, days: int = 7, work_type: str = "developer") -> Dict[str, Any]:
    # 1. Fetch real analytics
    real_data = calculate_analytics(session, days)
    
    # Check if we have real tracking data
    total_screen_time_sec = sum(real_data["total_screen_time"].values())
    
    if total_screen_time_sec > 0:
        # Build ONLINE data from real data
        total_dur = sum(item["duration_seconds"] for item in real_data["top_productive_apps"] + real_data["top_distracting_apps"])
        app_dist = []
        for item in real_data["top_productive_apps"] + real_data["top_distracting_apps"]:
            pct = (item["duration_seconds"] / (total_dur + 1e-6)) * 100.0
            app_dist.append({"app": item["app_name"], "usage": round(pct, 1)})
        if not app_dist:
            app_dist = [{"app": "VS Code", "usage": 100.0}]
            
        hourly_history = []
        for hr in range(9, 19): # 9 AM to 6 PM
            laptop_hr = (real_data["total_screen_time"].get("laptop", 0) / 10.0 / 3600.0)
            mobile_hr = (real_data["total_screen_time"].get("mobile", 0) / 10.0 / 3600.0)
            # Add variation
            var_l = 0.8 + 0.4 * (hr % 3)
            var_m = 0.5 + 0.3 * (hr % 2)
            hourly_history.append({
                "hour": f"{hr:02d}:00",
                "laptop": round(laptop_hr * var_l, 2),
                "mobile": round(mobile_hr * var_m, 2)
            })
            
        alerts = []
        if real_data["focus_efficiency"] < 40:
            alerts.append({
                "type": "warning",
                "message": f"Focus Efficiency is low ({real_data['focus_efficiency']}%). Deep work segments are fragmented."
            })
        if real_data["burnout_score"] > 50:
            alerts.append({
                "type": "critical",
                "message": f"Elevated Burnout Index: {real_data['burnout_score']}/100. Rest intervals are insufficient."
            })
        if not alerts:
            alerts.append({
                "type": "info",
                "message": "Focus states are stable. No overwork critical signals flagged."
            })
            
        recommendations = []
        if real_data["burnout_risk"] == "High" or real_data["burnout_risk"] == "Medium":
            recommendations.append({
                "title": "Mitigate Burnout Hazard",
                "action": "Disable notifications and disconnect by 9 PM tonight.",
                "impact": "Lowers burnout index and restores sleep latency."
            })
        if real_data["focus_efficiency"] < 30:
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
        event_stmt = select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(5)
        db_events = session.exec(event_stmt).all()
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
                "burnoutRisk": real_data["burnout_risk"].lower(),
                "productivityTrend": "stable" if real_data["productivity_score"] > 50 else "decreasing"
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

