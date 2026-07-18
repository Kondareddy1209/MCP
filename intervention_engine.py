"""
intervention_engine.py — it'syou Adaptive Intervention Engine
Runs periodic checks against live analytics and fires structured alerts when
behavioral thresholds are exceeded.

Fixes applied:
  C1: Reads correct payload key paths from the dashboard summary dict.
  C2: Added `from sqlmodel import select` import.
  C3: Delegates burnout scoring to BehaviorEngine.analyze_burnout() instead of
      duplicating the logic here with different thresholds.
"""
import time
import logging
from datetime import datetime, date
from sqlmodel import Session, select
from db import engine
from services.analytics import get_cached_dashboard_summary
from services.session_engine import SessionEngine
from services.behavior_engine import BehaviorEngine
from models import AppUsage, UsageEvent, AppClassification

# ─── Structured intervention logging ────────────────────────────────────────
logging.basicConfig(
    filename="interventions.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console_logger = logging.StreamHandler()
console_logger.setLevel(logging.INFO)
logging.getLogger().addHandler(console_logger)


class InterventionEngine:
    def __init__(self, check_interval_seconds: int = 60, cooldown_minutes: int = 15):
        self.check_interval = check_interval_seconds
        self.cooldown_period = cooldown_minutes * 60  # convert to seconds
        self.cooldowns: dict = {}  # {alert_type: last_trigger_timestamp}
        self.running = False

    def is_cooldown_active(self, alert_type: str) -> bool:
        last_time = self.cooldowns.get(alert_type)
        if last_time and (time.time() - last_time) < self.cooldown_period:
            return True
        return False

    def trigger_alert(self, alert_type: str, priority: str, message: str):
        """Dispatches an alert and updates cooldown tracker."""
        self.cooldowns[alert_type] = time.time()
        log_msg = f"[INTERVENTION] [{priority}] {message}"
        logging.info(log_msg)
        # Hook point: could send OS desktop notifications via win10toast or plyer

    def run_check(self):
        """Audits current active user metrics against baseline averages."""
        with Session(engine) as session:
            # Baseline: 7-day aggregate from analytics service (single source of truth)
            baseline = get_cached_dashboard_summary(session, 7)
            # Today: 1-day aggregate
            today_data = get_cached_dashboard_summary(session, 1)

        # C1 fix: use correct nested key paths from the dashboard summary payload.
        # The payload structure is: {"productivity": {"distracting_minutes": ...}, ...}
        baseline_dist_min = baseline.get("productivity", {}).get("distracting_minutes", 0.0)
        today_dist_min = today_data.get("productivity", {}).get("distracting_minutes", 0.0)

        # Convert minutes to seconds for threshold calculations
        avg_distraction_seconds = (baseline_dist_min / 7.0) * 60.0
        today_distraction_seconds = today_dist_min * 60.0
        today_productive_seconds = today_data.get("productivity", {}).get("productive_minutes", 0.0) * 60.0
        today_active_seconds = today_productive_seconds + today_distraction_seconds

        # ── Trigger 1: Distraction overload (> avg * 1.30 threshold) ────────────
        if avg_distraction_seconds > 0 and today_distraction_seconds > (avg_distraction_seconds * 1.30):
            if not self.is_cooldown_active("DISTRACTION_OVERLOAD"):
                priority = "HIGH" if today_distraction_seconds > (avg_distraction_seconds * 2.0) else "MEDIUM"
                mins = round(today_dist_min)
                msg = (
                    f"Distraction overload! You spent {mins} mins on distracting apps today, "
                    f"exceeding your {round(baseline_dist_min / 7.0, 1)}-min daily average by ≥30%."
                )
                self.trigger_alert("DISTRACTION_OVERLOAD", priority, msg)

        # ── Trigger 2: Burnout Alert (C3 fix — delegate to BehaviorEngine) ─────
        # Re-fetch raw sessions for burnout analysis so BehaviorEngine owns the math.
        try:
            with Session(engine) as session:
                today_date = date.today()
                from datetime import datetime, time as dtime
                start_ts = datetime.combine(today_date, dtime.min)
                usages = session.exec(
                    select(AppUsage).where(AppUsage.date == today_date)
                ).all()
                events = session.exec(
                    select(UsageEvent).where(UsageEvent.timestamp >= start_ts)
                ).all()

            sessions = SessionEngine.reconstruct_sessions(usages, events)
            burnout = BehaviorEngine.analyze_burnout(sessions)

            if burnout.score is not None and burnout.score > 70:
                if not self.is_cooldown_active("BURNOUT_WARNING"):
                    warnings_text = "; ".join(burnout.warnings) if burnout.warnings else "Overwork detected."
                    msg = (
                        f"🚨 High Burnout Risk (index {burnout.score}/100): {warnings_text} "
                        "Consider a mandatory lockoff or extended break."
                    )
                    self.trigger_alert("BURNOUT_WARNING", "HIGH", msg)

        except Exception as e:
            logging.error(f"Burnout check failed: {e}")

    def start_monitoring(self):
        self.running = True
        print("[+] it'syou Adaptive Intervention Engine started.")
        while self.running:
            try:
                self.run_check()
            except Exception as e:
                logging.error(f"Error in intervention check: {e}")
            time.sleep(self.check_interval)

    def stop_monitoring(self):
        self.running = False


if __name__ == "__main__":
    engine_inst = InterventionEngine(check_interval_seconds=60)
    try:
        engine_inst.start_monitoring()
    except KeyboardInterrupt:
        print("\n[*] Stopping Intervention Engine...")
        engine_inst.stop_monitoring()
