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
    timestamp: datetime.datetime = Field(default_factory=_ist_now, index=True)
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
    timestamp: datetime.datetime = Field(default_factory=_ist_now, index=True)
    app_name: str | None = None
    window_title: str | None = None
    metadata_json: str | None = None


class PushSubscription(SQLModel, table=True):
    __tablename__ = "push_subscriptions"
    id: int | None = Field(default=None, primary_key=True)
    endpoint: str = Field(index=True)
    subscription_json: str
    user_agent: str | None = None
    device: str = "mobile"
    created_at: datetime.datetime = Field(default_factory=_ist_now)


# ─── Pydantic Metrics & Health Models (SOLID Foundations) ───────────────
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ProductivityMetrics(BaseModel):
    score: Optional[int] = None
    productive_minutes: float = 0.0
    neutral_minutes: float = 0.0
    distracting_minutes: float = 0.0
    # Estimated score computed from auto_classify() regex when user has no
    # manual app_classifications. Distinct from `score` which requires real
    # user classifications. Presentation layer shows this as "~N% (estimated)".
    estimated_score: Optional[int] = None
    estimate_confidence: Optional[str] = None  # "auto-classified" | None

class FocusMetrics(BaseModel):
    focus_percentage: Optional[int] = None
    average_session: int = 0
    longest_session: int = 0
    deep_focus_count: int = 0
    switches_today: int = 0

class BurnoutMetrics(BaseModel):
    score: Optional[int] = None
    risk: Optional[str] = None
    warnings: List[str] = []

class DistractionCostMetrics(BaseModel):
    amount: Optional[float] = None
    currency: str = "INR"

class BehavioralInsightsMetrics(BaseModel):
    most_used_app: Optional[str] = None
    longest_session: Optional[str] = None
    most_productive_app: Optional[str] = None
    most_distracting_app: Optional[str] = None
    peak_productive_hour: Optional[str] = None
    peak_distraction_hour: Optional[str] = None
    average_session_duration: Optional[float] = None
    average_idle_duration: Optional[float] = None
    number_of_app_switches: int = 0
    daily_active_time: Optional[float] = None
    biggest_time_waster: Optional[str] = None
    spending_pattern: Optional[str] = None
    suggestion: Optional[str] = None

class TrackerHealthStatus(BaseModel):
    status: str  # "running" | "paused" | "stopped"
    paused: bool
    session_id: Optional[str] = None
    current_app: Optional[str] = None
    is_idle: bool = False

class DashboardSummaryMetrics(BaseModel):
    analytics: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    app_usage: List[Dict[str, Any]]
    screen_time: List[Dict[str, Any]]
    productivity: ProductivityMetrics
    focus: FocusMetrics
    burnout: BurnoutMetrics
    distraction_cost_details: DistractionCostMetrics
    insights: BehavioralInsightsMetrics
    recommendations: List[str]
    live_status: Dict[str, Any]


