from fastapi import APIRouter, Depends
from sqlmodel import Session
from db import get_session
from models import DailyScreenTime
from crud import get_screen_time, upsert_screen_time
from typing import List

router = APIRouter(prefix="/api/screen-time", tags=["Screen Time"])

@router.get("/", response_model=List[DailyScreenTime])
def read_screen_time(session: Session = Depends(get_session)):
    return get_screen_time(session)

@router.post("/", response_model=DailyScreenTime)
def record_screen_time(dst: DailyScreenTime, session: Session = Depends(get_session)):
    return upsert_screen_time(session, dst)
