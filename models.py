from sqlmodel import SQLModel, Field, UniqueConstraint
import datetime

class Expense(SQLModel, table=True):
    __tablename__ = "expenses"
    id: int | None = Field(default=None, primary_key=True)
    amount: float
    category: str
    description: str = ""
    date: datetime.date

class AppUsage(SQLModel, table=True):
    __tablename__ = "app_usage"
    id: int | None = Field(default=None, primary_key=True)
    app_name: str
    duration_seconds: int
    device: str  # 'mobile' or 'laptop'
    date: datetime.date
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    # Extended fields for activity intensity & session management
    session_id: str | None = None
    activity_score: float | None = 0.0
    input_events: int | None = 0
    idle_flag: bool | None = False
    device_type: str | None = "desktop"  # desktop or mobile

class DailyScreenTime(SQLModel, table=True):
    __tablename__ = "daily_screen_time"
    __table_args__ = (UniqueConstraint("date", "device", name="uq_date_device"),)
    id: int | None = Field(default=None, primary_key=True)
    total_time_seconds: int
    device: str
    date: datetime.date

class AppClassification(SQLModel, table=True):
    __tablename__ = "app_classifications"
    app_name: str = Field(primary_key=True)
    classification: str  # 'productive', 'distracting', 'neutral'

class ProductivityMetricsCache(SQLModel, table=True):
    __tablename__ = "productivity_metrics_cache"
    date: datetime.date = Field(primary_key=True)
    productivity_score: float
    distracting_time: int
    productive_time: int

class UsageEvent(SQLModel, table=True):
    __tablename__ = "usage_events"
    id: int | None = Field(default=None, primary_key=True)
    event_type: str  # APP_SWITCH, INPUT_ACTIVITY, IDLE_START, IDLE_END, SESSION_START, SESSION_END
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    app_name: str | None = None
    window_title: str | None = None
    metadata_json: str | None = None  # JSON string of metadata details
