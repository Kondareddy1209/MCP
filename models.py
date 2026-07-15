"""
models.py — itsyou_clean.db schema
All timestamps are IST-aware (Asia/Kolkata, UTC+5:30)
"""
from sqlmodel import SQLModel, Field, UniqueConstraint
import datetime


# ─── IST timezone helper ────────────────────────────────────────────────
try:
    import pytz
    _IST = pytz.timezone("Asia/Kolkata")
    def _ist_now() -> datetime.datetime:
        return datetime.datetime.now(_IST)
except ImportError:
    # pytz not installed → use fixed UTC+5:30 offset (no DST in IST)
    _IST_OFFSET = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    def _ist_now() -> datetime.datetime:
        return datetime.datetime.now(_IST_OFFSET)


# ─── Tables ─────────────────────────────────────────────────────────────

class Expense(SQLModel, table=True):
    __tablename__ = "expenses"
    id: int | None = Field(default=None, primary_key=True)
    amount: float
    category: str
    description: str = ""
    # date stored as local IST date
    date: datetime.date = Field(default_factory=lambda: _ist_now().date())


class AppUsage(SQLModel, table=True):
    """
    One row per tracked application session.
    Duplicate prevention: (app_name, date, timestamp) uniqueness is
    enforced at the CRUD layer (see crud.py) to allow flexible inserts.
    """
    __tablename__ = "app_usage"
    id: int | None = Field(default=None, primary_key=True)
    app_name: str
    duration_seconds: int = 0
    device: str = "laptop"               # 'laptop' | 'mobile'
    device_type: str = "desktop"         # 'desktop' | 'mobile'
    # ✅ IST date and timestamp — human-readable and timezone-correct
    date: datetime.date = Field(default_factory=lambda: _ist_now().date())
    timestamp: datetime.datetime = Field(default_factory=_ist_now)
    # Session metadata
    session_id: str | None = None
    activity_score: float = 0.0
    input_events: int = 0
    idle_flag: bool = False


class DailyScreenTime(SQLModel, table=True):
    __tablename__ = "daily_screen_time"
    __table_args__ = (UniqueConstraint("date", "device", name="uq_screen_date_device"),)
    id: int | None = Field(default=None, primary_key=True)
    total_time_seconds: int
    device: str
    date: datetime.date = Field(default_factory=lambda: _ist_now().date())


class AppClassification(SQLModel, table=True):
    __tablename__ = "app_classifications"
    app_name: str = Field(primary_key=True)
    classification: str  # 'productive' | 'distracting' | 'neutral'


class ProductivityMetricsCache(SQLModel, table=True):
    __tablename__ = "productivity_metrics_cache"
    date: datetime.date = Field(primary_key=True)
    productivity_score: float
    distracting_time: int
    productive_time: int


class UsageEvent(SQLModel, table=True):
    __tablename__ = "usage_events"
    id: int | None = Field(default=None, primary_key=True)
    event_type: str   # APP_SWITCH | INPUT_ACTIVITY | IDLE_START | IDLE_END
    timestamp: datetime.datetime = Field(default_factory=_ist_now)
    app_name: str | None = None
    window_title: str | None = None
    metadata_json: str | None = None
