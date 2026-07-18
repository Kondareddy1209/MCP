"""
services/behavior_engine.py — Behavior Engine Service
Cohesive service performing deterministic calculations on TrackedSession and UsageEvent objects.
No direct database/SQL queries.

Null-vs-estimated pattern:
  - `score` fields reflect only user-verified classifications from app_classifications table.
  - `estimated_score` fields are computed from auto_classify() regex heuristics.
  - Presentation layer renders score as "N%" and estimated_score as "~N% (estimated)".
  - Business layer NEVER emits placeholder strings ("Unknown", "N/A", etc.).
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, time
import math

from models import (
    ProductivityMetrics,
    FocusMetrics,
    BurnoutMetrics,
    DistractionCostMetrics,
    BehavioralInsightsMetrics,
    UsageEvent
)
from services.session_engine import TrackedSession
from classification import auto_classify


class BehaviorEngine:
    @staticmethod
    def analyze_productivity(sessions: List[TrackedSession], classifications: Dict[str, str]) -> ProductivityMetrics:
        """Calculates productivity score from app classifications.

        Two separate computations:
          - `score`: computed only when user has entries in app_classifications (not empty).
            Returns None when classifications dict is empty — "not configured" signal.
          - `estimated_score`: always computed using auto_classify() regex.
            Returns None only when there are zero active sessions.
        """
        productive_user = 0.0
        neutral_user = 0.0
        distracting_user = 0.0

        productive_auto = 0.0
        neutral_auto = 0.0
        distracting_auto = 0.0

        for s in sessions:
            if s.idle_flag or s.app_name == "SYSTEM_IDLE":
                continue

            app_clean = s.app_name.lower().strip()
            dur = s.duration_seconds

            # User classification (from DB)
            user_cls = classifications.get(app_clean)
            if user_cls == "productive":
                productive_user += dur
            elif user_cls == "distracting":
                distracting_user += dur
            else:
                neutral_user += dur  # covers "neutral" and "not classified by user"

            # Auto classification (regex heuristic)
            window_title_ctx = " ".join(s.window_titles) if s.window_titles else ""
            auto_cls = auto_classify(s.app_name, window_title_ctx)
            if auto_cls == "productive":
                productive_auto += dur
            elif auto_cls == "distracting":
                distracting_auto += dur
            else:
                neutral_auto += dur

        active_seconds = productive_user + neutral_user + distracting_user
        active_auto = productive_auto + neutral_auto + distracting_auto

        # Verified score: only when user has configured classifications
        score: Optional[int] = None
        if active_seconds > 0 and len(classifications) > 0:
            # Only count time that user has explicitly classified
            user_classified_seconds = 0.0
            user_productive_seconds = 0.0
            for s in sessions:
                if s.idle_flag or s.app_name == "SYSTEM_IDLE":
                    continue
                app_clean = s.app_name.lower().strip()
                if app_clean in classifications:
                    user_classified_seconds += s.duration_seconds
                    if classifications[app_clean] == "productive":
                        user_productive_seconds += s.duration_seconds
            if user_classified_seconds > 0:
                score = int((user_productive_seconds / user_classified_seconds) * 100)

        # Estimated score: auto-classify-based, always computed when sessions exist
        estimated_score: Optional[int] = None
        estimate_confidence: Optional[str] = None
        if active_auto > 0:
            estimated_score = int((productive_auto / active_auto) * 100)
            estimate_confidence = "auto-classified"

        return ProductivityMetrics(
            score=score,
            productive_minutes=round(productive_auto / 60.0, 1),
            neutral_minutes=round(neutral_auto / 60.0, 1),
            distracting_minutes=round(distracting_auto / 60.0, 1),
            estimated_score=estimated_score,
            estimate_confidence=estimate_confidence,
        )

    @staticmethod
    def analyze_focus(sessions: List[TrackedSession], events: List[UsageEvent]) -> FocusMetrics:
        """Calculates focus efficiency, deep work counts, and switches."""
        active_sessions = [s for s in sessions if not s.idle_flag and s.app_name != "SYSTEM_IDLE"]

        if not active_sessions:
            return FocusMetrics(
                focus_percentage=None,
                average_session=0,
                longest_session=0,
                deep_focus_count=0,
                switches_today=sum(1 for e in events if e.event_type == "focus")
            )

        durations = [s.duration_seconds for s in active_sessions]
        longest_session = int(max(durations) / 60) if durations else 0
        avg_session = int((sum(durations) / len(durations)) / 60) if durations else 0

        # Deep focus = sessions > 25 minutes (1500 seconds)
        deep_focus_count = sum(1 for d in durations if d > 1500)
        deep_focus_seconds = sum(d for d in durations if d > 1500)
        total_active_seconds = sum(durations)

        focus_percentage: Optional[int] = None
        if total_active_seconds > 0:
            focus_percentage = int((deep_focus_seconds / total_active_seconds) * 100)

        switches_today = sum(1 for e in events if e.event_type == "focus")

        return FocusMetrics(
            focus_percentage=focus_percentage,
            average_session=avg_session,
            longest_session=longest_session,
            deep_focus_count=deep_focus_count,
            switches_today=switches_today
        )

    @staticmethod
    def analyze_burnout(sessions: List[TrackedSession]) -> BurnoutMetrics:
        """Calculates burnout index and risk level based on workload patterns."""
        active_sessions = [s for s in sessions if not s.idle_flag and s.app_name != "SYSTEM_IDLE"]
        if not active_sessions:
            return BurnoutMetrics(score=None, risk=None, warnings=[])

        score = 10  # Baseline index
        warnings = []

        # 1. Continuous work blocks (> 2 hours without breaks)
        has_long_block = any(s.duration_seconds > 7200 for s in active_sessions)
        has_vlong_block = any(s.duration_seconds > 14400 for s in active_sessions)
        if has_vlong_block:
            score += 50
            warnings.append("Critical continuous work block: worked > 4 hours without break.")
        elif has_long_block:
            score += 30
            warnings.append("Continuous work block: worked > 2 hours without break.")

        # 2. Late-night work (11 PM - 5 AM)
        late_night_seconds = 0.0
        for s in active_sessions:
            if s.start_time.hour >= 23 or s.start_time.hour < 5:
                late_night_seconds += s.duration_seconds

        if late_night_seconds > 1800:  # > 30 mins late night
            score += 30
            warnings.append("Late-night workload: tracked active usage between 11 PM and 5 AM.")

        # 3. Daily workload volume (> 8 active hours)
        total_active_hours = sum(s.duration_seconds for s in active_sessions) / 3600.0
        if total_active_hours > 8.0:
            score += 20
            warnings.append("Extended screen hours: worked > 8 active hours today.")

        score = min(score, 100)

        # Determine risk level
        risk = "Low"
        if score > 70:
            risk = "High"
        elif score > 35:
            risk = "Moderate"

        return BurnoutMetrics(
            score=score,
            risk=risk,
            warnings=warnings
        )

    @staticmethod
    def analyze_distraction_cost(
        sessions: List[TrackedSession],
        classifications: Dict[str, str],
        hourly_rate: Optional[float]
    ) -> DistractionCostMetrics:
        """Calculates distraction financial opportunity cost.

        Uses auto_classify() as fallback when user has no manual classifications,
        so the cost is always computed when there are distracting sessions.
        """
        if hourly_rate is None or hourly_rate <= 0:
            return DistractionCostMetrics(amount=None, currency="INR")

        distracting_seconds = 0.0
        for s in sessions:
            if s.idle_flag or s.app_name == "SYSTEM_IDLE":
                continue
            app_clean = s.app_name.lower().strip()
            # User classification takes precedence; fall back to auto_classify
            window_title_ctx = " ".join(s.window_titles) if s.window_titles else ""
            classification = classifications.get(app_clean) or auto_classify(s.app_name, window_title_ctx)
            if classification == "distracting":
                distracting_seconds += s.duration_seconds

        distracting_hours = distracting_seconds / 3600.0
        cost = distracting_hours * hourly_rate
        return DistractionCostMetrics(
            amount=round(cost, 2),
            currency="INR"
        )

    @staticmethod
    def analyze_behavioral_insights(
        sessions: List[TrackedSession],
        classifications: Dict[str, str],
        events: List[UsageEvent]
    ) -> BehavioralInsightsMetrics:
        """Derives core behavioral insights and trends."""
        app_durations: Dict[str, float] = {}
        prod_durations: Dict[str, float] = {}
        dist_durations: Dict[str, float] = {}

        hourly_prod: Dict[int, float] = {h: 0.0 for h in range(24)}
        hourly_dist: Dict[int, float] = {h: 0.0 for h in range(24)}

        idle_seconds = 0.0
        active_seconds = 0.0

        for s in sessions:
            dur = s.duration_seconds
            if s.idle_flag or s.app_name == "SYSTEM_IDLE":
                idle_seconds += dur
                continue

            active_seconds += dur
            app = s.app_name
            app_durations[app] = app_durations.get(app, 0.0) + dur

            app_clean = app.lower().strip()
            # User classification takes precedence; fall back to auto_classify
            window_title_ctx = " ".join(s.window_titles) if s.window_titles else ""
            classification = classifications.get(app_clean) or auto_classify(app, window_title_ctx)

            if classification == "productive":
                prod_durations[app] = prod_durations.get(app, 0.0) + dur
                hourly_prod[s.start_time.hour] += dur
            elif classification == "distracting":
                dist_durations[app] = dist_durations.get(app, 0.0) + dur
                hourly_dist[s.start_time.hour] += dur

        most_used = max(app_durations, key=app_durations.get) if app_durations else None
        most_productive = max(prod_durations, key=prod_durations.get) if prod_durations else None
        most_distracting = max(dist_durations, key=dist_durations.get) if dist_durations else None

        peak_prod = max(hourly_prod, key=hourly_prod.get) if any(hourly_prod.values()) else -1
        peak_dist = max(hourly_dist, key=hourly_dist.get) if any(hourly_dist.values()) else -1

        peak_prod_str = f"{peak_prod:02d}:00" if peak_prod >= 0 else None
        peak_dist_str = f"{peak_dist:02d}:00" if peak_dist >= 0 else None

        session_durations = [s.duration_seconds for s in sessions if not s.idle_flag]
        avg_session = round(sum(session_durations) / len(session_durations) / 60.0, 1) if session_durations else None

        idle_durations = [s.duration_seconds for s in sessions if s.idle_flag]
        avg_idle = round(sum(idle_durations) / len(idle_durations) / 60.0, 1) if idle_durations else None

        longest_s = max(sessions, key=lambda s: s.duration_seconds) if sessions else None
        longest_s_str = f"{longest_s.app_name} ({round(longest_s.duration_seconds/60.0, 1)}m)" if longest_s else None

        num_switches = sum(1 for e in events if e.event_type == "focus")
        daily_active = round(active_seconds / 3600.0, 1) if active_seconds > 0 else None

        biggest_waster = most_distracting
        if not biggest_waster and most_used:
            biggest_waster = f"No distracting apps classified — most-used: {most_used}"

        return BehavioralInsightsMetrics(
            most_used_app=most_used,
            longest_session=longest_s_str,
            most_productive_app=most_productive,
            most_distracting_app=most_distracting,
            peak_productive_hour=peak_prod_str,
            peak_distraction_hour=peak_dist_str,
            average_session_duration=avg_session,
            average_idle_duration=avg_idle,
            number_of_app_switches=num_switches,
            daily_active_time=daily_active,
            biggest_time_waster=biggest_waster,
            spending_pattern=None,
            suggestion=None
        )

    @staticmethod
    def generate_recommendations(prod_score: Optional[int], switches: int, max_session_seconds: float) -> List[str]:
        """Rule-based recommendations engine."""
        recs = []
        if switches > 30:
            recs.append("Frequent context switching detected. Try batching similar tasks into 25-minute blocks to save focus.")
        if max_session_seconds > 5400:  # > 90 mins
            recs.append("You worked for over 90 minutes without a break. Stand up, stretch, and give your eyes a 5-minute screen break.")
        if prod_score is not None and prod_score < 50:
            recs.append("Distractions are elevated today. Consider placing distracting apps on a temporary focus-block list.")

        if not recs:
            recs.append("Excellent pacing! Maintain your current work-to-break intervals.")
        return recs

    @staticmethod
    def detect_habits(sessions: List[TrackedSession], events: List[UsageEvent]) -> List[str]:
        """Calculates work habits based on real usage patterns."""
        habits = []
        if not sessions:
            return habits
            
        active_sessions = [s for s in sessions if not s.idle_flag and s.app_name != "SYSTEM_IDLE"]
        if active_sessions:
            # 1. Start time of day
            earliest_start = min(s.start_time for s in active_sessions)
            if earliest_start.hour < 10:
                habits.append(f"Morning focus block starts before 10:00 AM (earliest: {earliest_start.strftime('%H:%M')})")
                
            # Late night work
            late_sessions = [s for s in active_sessions if s.start_time.hour >= 23 or s.start_time.hour < 5]
            if len(late_sessions) > 0:
                habits.append(f"Late-night work patterns: active sessions detected after 11:00 PM")
                
        # 2. Main application usage
        app_durations = {}
        for s in active_sessions:
            app_durations[s.app_name] = app_durations.get(s.app_name, 0.0) + s.duration_seconds
        if app_durations:
            top_app = max(app_durations, key=app_durations.get)
            hours = app_durations[top_app] / 3600.0
            if hours > 1.0:
                habits.append(f"Core tool habituation: high focus on {top_app} ({round(hours, 1)} hrs)")
                
        # 3. Context switches
        switches = sum(1 for e in events if e.event_type == "focus")
        if switches > 30:
            habits.append(f"Multitasking loop: frequent context switching ({switches} app switches)")
        elif 0 < switches <= 10:
            habits.append("Deep concentration clusters: low application switching rate")
            
        # 4. Longest uninterrupted focus
        longest = max((s.duration_seconds for s in active_sessions), default=0)
        if longest > 1800: # >30m
            habits.append(f"Extended focus sprint: uninterrupted {round(longest/60, 1)}m session")

        if not habits:
            habits.append("Establishing baseline work habits...")
            
        return habits
