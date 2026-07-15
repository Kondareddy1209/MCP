from fastapi import APIRouter, Depends
from sqlmodel import Session
from db import get_session
from models import UsageEvent
from crud import create_usage_event, bulk_create_usage_events, get_usage_events
from typing import List

router = APIRouter(prefix="/api/events", tags=["Usage Events"])

@router.post("/", response_model=UsageEvent)
def add_event(event: UsageEvent, session: Session = Depends(get_session)):
    return create_usage_event(session, event)

@router.post("/bulk", response_model=List[UsageEvent])
def add_events_bulk(events: List[UsageEvent], session: Session = Depends(get_session)):
    return bulk_create_usage_events(session, events)

@router.get("/", response_model=List[UsageEvent])
def read_events(limit: int = 100, session: Session = Depends(get_session)):
    return get_usage_events(session, limit)
