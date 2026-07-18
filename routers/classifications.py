from fastapi import APIRouter, Depends
from sqlmodel import Session
from db import get_session
from models import AppClassification
from crud import get_classifications, upsert_classification
from typing import List

router = APIRouter(prefix="/api/classifications", tags=["Classifications"])

@router.get("/", response_model=List[AppClassification])
def read_classifications(session: Session = Depends(get_session)):
    return get_classifications(session)

@router.post("/", response_model=AppClassification)
def record_classification(classification: AppClassification, session: Session = Depends(get_session)):
    res = upsert_classification(session, classification)
    from services.analytics import invalidate_analytics_cache
    invalidate_analytics_cache()
    return res
