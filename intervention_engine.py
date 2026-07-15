import time
import logging
from datetime import datetime, date
from sqlmodel import Session
from db import engine
import analytics

# Setup structured intervention logging
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
        self.cooldowns = {}  # {alert_type: last_trigger_timestamp}
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
        
        # Here we could hook in OS desktop notifications:
        # e.g., using win10toast or plyer if installed, or writing to a dynamic backend notifications table.

    def run_check(self):
        """Audits current active user metrics against baseline averages."""
        with Session(engine) as session:
            # 1. Fetch baseline average (last 7 days)
            baseline = analytics.calculate_analytics(session, 7)
            # 2. Fetch today's current usage (last 1 day)
            today = analytics.calculate_analytics(session, 1)

        # Baseline calculations (divided by 7 to get daily average)
        avg_distraction_seconds = baseline["distracting_time_seconds"] / 7.0
        
        today_distraction_seconds = today["distracting_time_seconds"]
        today_active_seconds = today["productive_time_seconds"] + today_distraction_seconds
        total_usage_hours = today_active_seconds / 3600.0

        # Trigger 1: Distraction overload (> avg * threshold)
        # Threshold is set to 1.30 (30% above average)
        if avg_distraction_seconds > 0 and today_distraction_seconds > (avg_distraction_seconds * 1.30):
            if not self.is_cooldown_active("DISTRACTION_OVERLOAD"):
                priority = "HIGH" if today_distraction_seconds > (avg_distraction_seconds * 2.0) else "MEDIUM"
                msg = f"Distraction overload! You spent {round(today_distraction_seconds/60)} mins on distracting apps today, exceeding your average by 30%."
                self.trigger_alert("DISTRACTION_OVERLOAD", priority, msg)

        # Trigger 2: Burnout Alert (usage > 8 hours AND late night usage after 11 PM)
        has_late_night = False
        with Session(engine) as session:
            from models import AppUsage
            today_usages = session.exec(select(AppUsage).where(AppUsage.date == date.today())).all()
            for u in today_usages:
                ts = u.timestamp
                if isinstance(ts, str):
                    try:
                        cleaned = ts.replace("Z", "").split(".")[0]
                        ts = datetime.strptime(cleaned, "%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        continue
                if ts.hour >= 23 or ts.hour < 4:
                    has_late_night = True
                    break

        if total_usage_hours > 8.0 and has_late_night:
            if not self.is_cooldown_active("BURNOUT_WARNING"):
                msg = "🚨 Critical Overwork Warning: You've exceeded 8 hours of usage today with active late-night sessions. Mandatory lockoff recommended!"
                self.trigger_alert("BURNOUT_WARNING", "HIGH", msg)


    def start_monitoring(self):
        self.running = True
        print("[+] Antigravity Adaptive Intervention Engine started.")
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
