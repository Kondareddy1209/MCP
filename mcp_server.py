from mcp.server.fastmcp import FastMCP
from sqlmodel import Session
from datetime import date
import json

from db import engine
import crud
import analytics
from models import Expense, DailyScreenTime, AppClassification

# Initialize FastMCP server
mcp = FastMCP("Antigravity")

@mcp.tool()
def get_daily_summary() -> str:
    """Gets a comprehensive report of today's focus metrics, burnout risk, and personalized habits/coaching tips."""
    with Session(engine) as session:
        data = analytics.calculate_analytics(session, 1)
        summary = {
            "productivity_score": f"{data['productivity_score']}%",
            "focus_efficiency": f"{data['focus_efficiency']}%",
            "burnout_score": f"{data['burnout_score']}/100 ({data['burnout_risk']} Risk)",
            "total_expenses_today": f"{data['currency']} {data['total_spent']}",
            "biggest_time_waster": data["insights"]["biggest_time_waster"],
            "habit_insights": f"Peak productivity hour: {data['peak_productivity_hour']}:00 | Habits: {', '.join(data['detected_habits']) if data['detected_habits'] else 'None'}",
            "suggestion": data["insights"]["suggestion"]
        }
        return json.dumps(summary, indent=2)

@mcp.tool()
def get_productivity_score(days: int = 7) -> str:
    """Calculates your advanced productivity score for the last N days (deep work weighted at 1.5x)."""
    with Session(engine) as session:
        data = analytics.calculate_analytics(session, days)
        return f"Productivity Score (Last {days} days): {data['productivity_score']}%"

@mcp.tool()
def get_burnout_score(days: int = 7) -> str:
    """Calculates your behavioral burnout index (0-100) and risk level for the last N days."""
    with Session(engine) as session:
        data = analytics.calculate_analytics(session, days)
        return f"Burnout Index: {data['burnout_score']}/100 | Risk Category: {data['burnout_risk']}"

@mcp.tool()
def classify_app(app_name: str, classification: str) -> str:
    """Saves or updates application classification ('productive', 'distracting', or 'neutral')."""
    class_clean = classification.lower().strip()
    if class_clean not in ["productive", "distracting", "neutral"]:
        return "Error: classification must be 'productive', 'distracting', or 'neutral'."
        
    ac = AppClassification(app_name=app_name, classification=class_clean)
    with Session(engine) as session:
        crud.upsert_classification(session, ac)
        return f"Application '{app_name}' successfully classified as '{class_clean}'."

@mcp.tool()
def log_expense(amount: float, category: str, description: str = "", date_str: str = None) -> str:
    """Logs a new expense. date_str should be in YYYY-MM-DD format (defaults to today)."""
    exp_date = date.today()
    if date_str:
        try:
            exp_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return "Error: date_str must be in YYYY-MM-DD format."
            
    expense = Expense(amount=amount, category=category.lower().strip(), description=description, date=exp_date)
    with Session(engine) as session:
        crud.create_expense(session, expense)
        return f"Expense logged successfully: {amount} for {category} on {exp_date}."

if __name__ == "__main__":
    mcp.run()
