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
    data = calculate_analytics(session, 1)
    return {
        "productivity_score": data["productivity_score"],
        "focus_efficiency": data["focus_efficiency"],
        "burnout_score": data["burnout_score"],
        "burnout_risk": data["burnout_risk"],
        "total_spent": data["total_spent"],
        "currency": data["currency"],
        "biggest_time_waster": data["insights"]["biggest_time_waster"],
        "peak_productivity_hour": data["peak_productivity_hour"],
        "detected_habits": data["detected_habits"],
        "suggestion": data["insights"]["suggestion"]
    }

