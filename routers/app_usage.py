from fastapi import APIRouter, Depends
from sqlmodel import Session
from db import get_session
from models import AppUsage
from crud import get_app_usage, create_app_usage, bulk_create_app_usage
from typing import List

router = APIRouter(prefix="/api/app-usage", tags=["App Usage"])

@router.get("/", response_model=List[AppUsage])
def read_app_usage(session: Session = Depends(get_session)):
    return get_app_usage(session)

@router.post("/", response_model=AppUsage)
def add_app_usage(app_usage: AppUsage, session: Session = Depends(get_session)):
    return create_app_usage(session, app_usage)

@router.post("/bulk", response_model=List[AppUsage])
def add_app_usage_bulk(app_usages: List[AppUsage], session: Session = Depends(get_session)):
    return bulk_create_app_usage(session, app_usages)
