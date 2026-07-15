"""
crud.py — Database operations for itsyou_clean.db
Duplicate prevention on AppUsage: (app_name, date, timestamp rounded to second)
All timestamps are IST-aware.
"""
from sqlmodel import Session, select
from datetime import date, datetime, timezone, timedelta
from models import Expense, AppUsage, DailyScreenTime, AppClassification, ProductivityMetricsCache, UsageEvent
from typing import List

# ─── IST timezone helper ────────────────────────────────────────────────
try:
    import pytz
    _IST = pytz.timezone("Asia/Kolkata")
    def _ist_now() -> datetime:
        return datetime.now(_IST)
except ImportError:
    _IST_OFFSET = timezone(timedelta(hours=5, minutes=30))
    def _ist_now() -> datetime:
        return datetime.now(_IST_OFFSET)


# ─── Coerce / Normalize incoming fields ─────────────────────────────────
def _coerce_date(obj):
    """Convert string date/timestamp fields to Python objects."""
    if hasattr(obj, "date") and isinstance(obj.date, str):
        try:
            obj.date = datetime.strptime(obj.date, "%Y-%m-%d").date()
        except ValueError:
            pass

    if hasattr(obj, "timestamp") and isinstance(obj.timestamp, str):
        try:
            cleaned = obj.timestamp.replace("Z", "").strip()
            cleaned = cleaned.split(".")[0]  # strip microseconds
            if "T" in cleaned:
                obj.timestamp = datetime.strptime(cleaned, "%Y-%m-%dT%H:%M:%S")
            else:
                obj.timestamp = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            obj.timestamp = _ist_now()

    return obj


def _round_ts_to_second(ts: datetime) -> datetime:
    """Strip microseconds for dedup comparison."""
    return ts.replace(microsecond=0) if ts else ts


# ─── Expenses ────────────────────────────────────────────────────────────
def get_expenses(session: Session) -> List[Expense]:
    return session.exec(select(Expense).order_by(Expense.date.desc())).all()


def create_expense(session: Session, expense: Expense) -> Expense:
    _coerce_date(expense)
    if not expense.date:
        expense.date = _ist_now().date()
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


# ─── App Usage ───────────────────────────────────────────────────────────
def get_app_usage(session: Session) -> List[AppUsage]:
    return session.exec(select(AppUsage).order_by(AppUsage.date.desc())).all()


def _is_duplicate_usage(session: Session, item: AppUsage) -> bool:
    """
    Duplicate detection:
    A record is a duplicate if same (app_name, date) already has an entry
    within ±1 second of the incoming timestamp.
    """
    if not item.timestamp or not item.date:
        return False

    ts_rounded = _round_ts_to_second(item.timestamp)

    existing = session.exec(
        select(AppUsage).where(
            AppUsage.app_name == item.app_name,
            AppUsage.date == item.date
        )
    ).all()

    for rec in existing:
        if rec.timestamp and _round_ts_to_second(rec.timestamp) == ts_rounded:
            return True
    return False


def create_app_usage(session: Session, app_usage: AppUsage) -> AppUsage:
    _coerce_date(app_usage)
    if not app_usage.device_type:
        app_usage.device_type = "desktop"
    if not app_usage.date:
        app_usage.date = _ist_now().date()
    if not app_usage.timestamp:
        app_usage.timestamp = _ist_now()

    if _is_duplicate_usage(session, app_usage):
        # Return the existing record silently — don't insert duplicate
        existing = session.exec(
            select(AppUsage).where(
                AppUsage.app_name == app_usage.app_name,
                AppUsage.date == app_usage.date
            )
        ).first()
        return existing or app_usage

    session.add(app_usage)
    session.commit()
    session.refresh(app_usage)
    return app_usage


def bulk_create_app_usage(session: Session, app_usages: List[AppUsage]) -> List[AppUsage]:
    results = []
    for item in app_usages:
        _coerce_date(item)
        if not item.device_type:
            item.device_type = "desktop"
        if not item.date:
            item.date = _ist_now().date()
        if not item.timestamp:
            item.timestamp = _ist_now()

        if not _is_duplicate_usage(session, item):
            session.add(item)
            results.append(item)
        # else: silently skip duplicate

    session.commit()
    for item in results:
        try:
            session.refresh(item)
        except Exception:
            pass
    return results


# ─── Daily Screen Time ───────────────────────────────────────────────────
def get_screen_time(session: Session) -> List[DailyScreenTime]:
    return session.exec(select(DailyScreenTime).order_by(DailyScreenTime.date.desc())).all()


def upsert_screen_time(session: Session, dst: DailyScreenTime) -> DailyScreenTime:
    _coerce_date(dst)
    if not dst.date:
        dst.date = _ist_now().date()

    existing = session.exec(
        select(DailyScreenTime).where(
            DailyScreenTime.date == dst.date,
            DailyScreenTime.device == dst.device
        )
    ).first()

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


# ─── App Classification ──────────────────────────────────────────────────
def get_classifications(session: Session) -> List[AppClassification]:
    return session.exec(select(AppClassification)).all()


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


# ─── Productivity Metrics Cache ───────────────────────────────────────────
def get_cached_metrics(session: Session) -> List[ProductivityMetricsCache]:
    return session.exec(select(ProductivityMetricsCache).order_by(ProductivityMetricsCache.date.desc())).all()


def upsert_cached_metrics(session: Session, metrics: ProductivityMetricsCache) -> ProductivityMetricsCache:
    _coerce_date(metrics)
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


# ─── Usage Events ─────────────────────────────────────────────────────────
def create_usage_event(session: Session, event: UsageEvent) -> UsageEvent:
    _coerce_date(event)
    if not event.timestamp:
        event.timestamp = _ist_now()
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def bulk_create_usage_events(session: Session, events: List[UsageEvent]) -> List[UsageEvent]:
    for e in events:
        _coerce_date(e)
        if not e.timestamp:
            e.timestamp = _ist_now()
        session.add(e)
    session.commit()
    for e in events:
        try:
            session.refresh(e)
        except Exception:
            pass
    return events


def get_usage_events(session: Session, limit: int = 100) -> List[UsageEvent]:
    return session.exec(
        select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(limit)
    ).all()
