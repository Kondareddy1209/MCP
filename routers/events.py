from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from db import get_session
from models import UsageEvent, AppUsage
from crud import create_usage_event, bulk_create_usage_events, get_usage_events
from typing import List
from datetime import datetime, timezone, timedelta

# Import the WS connection manager
from ws_manager import manager

router = APIRouter(prefix="/api/events", tags=["Usage Events"])

def ist_now() -> datetime:
    try:
        import pytz
        return datetime.now(pytz.timezone("Asia/Kolkata"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))

@router.post("/", response_model=UsageEvent)
async def add_event(event: UsageEvent, session: Session = Depends(get_session)):
    created = create_usage_event(session, event)
    
    # Invalidate cache (Task 13)
    from services.analytics import invalidate_analytics_cache
    invalidate_analytics_cache()
    
    # Send WebSocket broadcast (STEP 1 & STEP 5)
    try:
        status = "inactive" if created.event_type in ["blur", "IDLE_START", "SESSION_END", "idle"] or created.app_name == "SYSTEM_IDLE" else "active"
        last_active = {
            "app": created.app_name or "None",
            "window": created.window_title or "None",
            "timestamp": created.timestamp.isoformat(),
            "status": status
        }
        delta_event = {
            "id": created.id,
            "event_type": created.event_type,
            "app_name": created.app_name,
            "window_title": created.window_title,
            "timestamp": created.timestamp.isoformat()
        }
        
        # Today's summary
        today = ist_now().date()
        usages = session.exec(select(AppUsage).where(AppUsage.date == today)).all()
        updated_summary = {}
        for u in usages:
            updated_summary[u.app_name] = updated_summary.get(u.app_name, 0) + u.duration_seconds
            
        # Get the latest current_activity from analytics service
        from services.analytics import compute_dashboard_summary
        summary = compute_dashboard_summary(session, days=1)
        curr_act = summary.get("current_activity")

        payload = {
            "last_active": last_active,
            "delta_event": delta_event,
            "updated_summary": updated_summary,
            "current_activity": curr_act
        }
        
        # Broadcast via manager
        await manager.broadcast(payload)
    except Exception as e:
        print(f"[WebSocket] Broadcast error: {e}")
        
    return created

@router.post("/bulk", response_model=List[UsageEvent])
def add_events_bulk(events: List[UsageEvent], session: Session = Depends(get_session)):
    return bulk_create_usage_events(session, events)

@router.get("/", response_model=List[UsageEvent])
def read_events(limit: int = 100, session: Session = Depends(get_session)):
    return get_usage_events(session, limit)
