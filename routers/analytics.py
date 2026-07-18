from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from db import get_session
from analytics import calculate_analytics

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/")
def get_analytics(days: int = Query(default=7, ge=1), session: Session = Depends(get_session)):
    return calculate_analytics(session, days)

@router.get("/daily-summary")
def get_daily_summary(session: Session = Depends(get_session)):
    """Returns a condensed daily summary. Fixed C4: uses correct nested key paths."""
    data = calculate_analytics(session, 1)
    insights = data.get("insights", {})
    return {
        "productivity_score": data.get("productivity_score"),
        "estimated_score": data.get("estimated_score"),
        "estimate_confidence": data.get("estimate_confidence"),
        "focus_efficiency": data.get("focus_efficiency"),
        "burnout_score": data.get("burnout_score"),
        "burnout_risk": data.get("burnout_risk"),
        "total_spent": data.get("total_spent"),
        "currency": data.get("currency"),
        # Fixed C4: was data["peak_productivity_hour"] — key does not exist at top level.
        # Correct path is insights["peak_productive_hour"].
        "peak_productivity_hour": insights.get("peak_productive_hour"),
        "biggest_time_waster": insights.get("biggest_time_waster"),
        "detected_habits": data.get("detected_habits", []),
        "suggestion": insights.get("suggestion"),
    }
