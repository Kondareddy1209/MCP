"""
analytics.py — Backward-compatibility shim redirecting to services/analytics.py.

Only thin wrappers live here. Do NOT add business logic.
The broken calculate_focus_sessions() function (which did `datetime + int`,
a TypeError) has been removed — it was dead code with no callers.
"""
from sqlmodel import Session
from typing import Dict, Any

from services.analytics import (
    compute_dashboard_summary,
    get_cached_dashboard_summary,
    invalidate_analytics_cache,
    generate_ai_dashboard,
)
# Re-export auto_classify so existing imports like `from analytics import auto_classify` work
from classification import auto_classify


def calculate_analytics(session: Session, days: int = 7) -> Dict[str, Any]:
    """Returns the cached dashboard summary containing all computed metrics."""
    return get_cached_dashboard_summary(session, days)
