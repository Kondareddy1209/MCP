from sqlmodel import Session, select
from datetime import date, datetime
from models import Expense, AppUsage, DailyScreenTime, AppClassification, ProductivityMetricsCache, UsageEvent
from typing import List, Optional

def coerce_date(obj):
    if hasattr(obj, "date") and isinstance(obj.date, str):
        try:
            obj.date = datetime.strptime(obj.date, "%Y-%m-%d").date()
        except ValueError:
            pass
    if hasattr(obj, "timestamp") and isinstance(obj.timestamp, str):
        try:
            cleaned = obj.timestamp.replace("Z", "")
            if "." in cleaned:
                cleaned = cleaned.split(".")[0]
            if "T" in cleaned:
                obj.timestamp = datetime.strptime(cleaned, "%Y-%m-%dT%H:%M:%S")
            else:
                obj.timestamp = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

# Expenses CRUD
def get_expenses(session: Session) -> List[Expense]:
    statement = select(Expense).order_by(Expense.date.desc())
    return session.exec(statement).all()

def create_expense(session: Session, expense: Expense) -> Expense:
    coerce_date(expense)
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense

def delete_expense(session: Session, expense_id: int) -> bool:
    expense = session.get(Expense, expense_id)
    if expense:
        session.delete(expense)
        session.commit()
        return True
    return False

# App Usage CRUD
def get_app_usage(session: Session) -> List[AppUsage]:
    statement = select(AppUsage).order_by(AppUsage.date.desc())
    return session.exec(statement).all()

def create_app_usage(session: Session, app_usage: AppUsage) -> AppUsage:
    coerce_date(app_usage)
    # Enforce device type if none
    if not app_usage.device_type:
        app_usage.device_type = "desktop"
    session.add(app_usage)
    session.commit()
    session.refresh(app_usage)
    return app_usage

def bulk_create_app_usage(session: Session, app_usages: List[AppUsage]) -> List[AppUsage]:
    for item in app_usages:
        coerce_date(item)
        if not item.device_type:
            item.device_type = "desktop"
        session.add(item)
    session.commit()
    for item in app_usages:
        session.refresh(item)
    return app_usages

# Daily Screen Time CRUD
def get_screen_time(session: Session) -> List[DailyScreenTime]:
    statement = select(DailyScreenTime).order_by(DailyScreenTime.date.desc())
    return session.exec(statement).all()

def upsert_screen_time(session: Session, dst: DailyScreenTime) -> DailyScreenTime:
    coerce_date(dst)
    statement = select(DailyScreenTime).where(
        DailyScreenTime.date == dst.date,
        DailyScreenTime.device == dst.device
    )
    existing = session.exec(statement).first()
    if existing:
        existing.total_time_seconds = dst.total_time_seconds
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    else:
        session.add(dst)
        session.commit()
        session.refresh(dst)
        return dst

# App Classification CRUD
def get_classifications(session: Session) -> List[AppClassification]:
    statement = select(AppClassification)
    return session.exec(statement).all()

def upsert_classification(session: Session, classification: AppClassification) -> AppClassification:
    existing = session.get(AppClassification, classification.app_name)
    if existing:
        existing.classification = classification.classification
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    else:
        session.add(classification)
        session.commit()
        session.refresh(classification)
        return classification

# Cache CRUD
def get_cached_metrics(session: Session) -> List[ProductivityMetricsCache]:
    statement = select(ProductivityMetricsCache).order_by(ProductivityMetricsCache.date.desc())
    return session.exec(statement).all()

def upsert_cached_metrics(session: Session, metrics: ProductivityMetricsCache) -> ProductivityMetricsCache:
    coerce_date(metrics)
    existing = session.get(ProductivityMetricsCache, metrics.date)
    if existing:
        existing.productivity_score = metrics.productivity_score
        existing.distracting_time = metrics.distracting_time
        existing.productive_time = metrics.productive_time
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    else:
        session.add(metrics)
        session.commit()
        session.refresh(metrics)
        return metrics

# Usage Events CRUD
def create_usage_event(session: Session, event: UsageEvent) -> UsageEvent:
    coerce_date(event)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

def bulk_create_usage_events(session: Session, events: List[UsageEvent]) -> List[UsageEvent]:
    for e in events:
        coerce_date(e)
        session.add(e)
    session.commit()
    for e in events:
        session.refresh(e)
    return events

def get_usage_events(session: Session, limit: int = 100) -> List[UsageEvent]:
    statement = select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(limit)
    return session.exec(statement).all()
