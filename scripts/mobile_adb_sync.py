"""Background sync daemon for Android usage collection via ADB wireless debugging."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classification import normalize_app_name


logger = logging.getLogger(__name__)

try:
    import pytz

    _IST = pytz.timezone("Asia/Kolkata")

    def ist_now() -> datetime:
        return datetime.now(_IST)
except Exception:
    _IST_OFFSET = timezone(timedelta(hours=5, minutes=30))

    def ist_now() -> datetime:
        return datetime.now(_IST_OFFSET)


EVENT_START_MARKERS = (
    "move_to_foreground",
    "activity_resumed",
    "foreground",
    "resume",
    "start",
)
EVENT_END_MARKERS = (
    "move_to_background",
    "activity_paused",
    "background",
    "pause",
    "stop",
)


@dataclass
class MobileSession:
    app: str
    start_time: datetime
    end_time: datetime

    @property
    def duration_seconds(self) -> int:
        return max(0, int((self.end_time - self.start_time).total_seconds()))


def load_runtime_config(config_path: str = "config.json") -> Dict[str, object]:
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def load_state(state_path: str) -> Dict[str, object]:
    if not os.path.exists(state_path):
        return {"last_synced_timestamp": None}
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {"last_synced_timestamp": None}


def save_state(state_path: str, state: Dict[str, object]) -> None:
    directory = os.path.dirname(state_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def _adb_command(args: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout, check=False)


def adb_connect(host: str, port: int) -> bool:
    result = _adb_command(["connect", f"{host}:{port}"], timeout=10)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0 and any(token in output.lower() for token in ["connected", "already connected"])


def dumpsys_usagestats(use_history: bool = True) -> str:
    args = ["shell", "dumpsys", "usagestats"]
    if use_history:
        args.append("--history")
    result = _adb_command(args, timeout=30)
    return (result.stdout or "") + (result.stderr or "")


def _parse_timestamp(raw: str) -> Optional[datetime]:
    raw = raw.strip().replace("Z", "+00:00")
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]
    for pattern in patterns:
        try:
            parsed = datetime.strptime(raw, pattern)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=ist_now().tzinfo)
        except Exception:
            continue
    try:
        numeric = int(raw)
        if numeric > 10**12:
            numeric = numeric / 1000
        return datetime.fromtimestamp(numeric, tz=ist_now().tzinfo)
    except Exception:
        return None


def parse_usagestats_output(output: str) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    if not output:
        return events

    pattern_candidates = [
        re.compile(
            r"(?P<timestamp>(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\d{10,13}))"
            r".*?(?:mPackage|package|pkg)=?(?P<package>[A-Za-z0-9_\.]+)"
            r".*?(?:mEventType|eventType|event type|type)=?(?P<event_type>[A-Za-z0-9_\-]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?P<package>[A-Za-z0-9_\.]+).*?(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\d{10,13}).*?(?P<event_type>[A-Za-z0-9_\-]+)",
            re.IGNORECASE,
        ),
    ]

    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = None
        for pattern in pattern_candidates:
            match = pattern.search(stripped)
            if match:
                break
        if not match:
            continue

        timestamp = _parse_timestamp(match.group("timestamp"))
        if not timestamp:
            continue
        package = match.group("package").strip()
        event_type = match.group("event_type").strip().lower()
        events.append({"timestamp": timestamp, "package": package, "event_type": event_type, "raw": stripped})

    events.sort(key=lambda item: item["timestamp"])
    return events


def reconstruct_sessions(events: List[Dict[str, object]]) -> List[MobileSession]:
    active: Dict[str, Dict[str, object]] = {}
    sessions: List[MobileSession] = []

    for event in events:
        package = str(event.get("package") or "").strip()
        timestamp = event.get("timestamp")
        event_type = str(event.get("event_type") or "").lower()
        if not package or not isinstance(timestamp, datetime):
            continue

        if any(marker in event_type for marker in EVENT_START_MARKERS):
            active[package] = event
            continue

        if any(marker in event_type for marker in EVENT_END_MARKERS):
            start_event = active.pop(package, None)
            if start_event:
                start_time = start_event["timestamp"]
                if isinstance(start_time, datetime) and timestamp > start_time:
                    sessions.append(MobileSession(app=package, start_time=start_time, end_time=timestamp))

    return sessions


class MobileAdbSyncDaemon:
    def __init__(self, backend_api: str = "http://localhost:8000/api", config_path: str = "config.json"):
        self.backend_api = backend_api.rstrip("/")
        self.config_path = config_path
        cfg = load_runtime_config(config_path).get("mobile_adb", {}) if isinstance(load_runtime_config(config_path), dict) else {}
        self.host = str(cfg.get("ip") or "")
        self.port = int(cfg.get("port") or 0)
        self.poll_interval_seconds = int(cfg.get("poll_interval_seconds") or 30)
        self.state_path = str(cfg.get("state_file") or ".mobile_adb_sync_state.json")
        self.running = False

    def _load_checkpoint(self) -> Optional[datetime]:
        state = load_state(self.state_path)
        raw_value = state.get("last_synced_timestamp")
        if not raw_value:
            return None
        if isinstance(raw_value, str):
            return _parse_timestamp(raw_value)
        return None

    def _save_checkpoint(self, checkpoint: datetime) -> None:
        save_state(self.state_path, {"last_synced_timestamp": checkpoint.isoformat()})

    def _pick_output(self, history_output: str, legacy_output: str) -> str:
        if parse_usagestats_output(history_output):
            return history_output
        if parse_usagestats_output(legacy_output):
            return legacy_output
        return history_output or legacy_output

    def sync_once(self) -> Dict[str, object]:
        if not self.host or not self.port:
            return {"synced": False, "reason": "mobile_adb_not_configured"}

        if not adb_connect(self.host, self.port):
            return {"synced": False, "reason": "device_unreachable"}

        history_output = dumpsys_usagestats(use_history=True)
        legacy_output = dumpsys_usagestats(use_history=False)
        output = self._pick_output(history_output, legacy_output)
        events = parse_usagestats_output(output)
        checkpoint = self._load_checkpoint()
        filtered_events = [event for event in events if not checkpoint or event["timestamp"] > checkpoint]
        sessions = reconstruct_sessions(filtered_events)

        if not sessions:
            return {"synced": True, "sessions": 0, "apps": [], "total_duration": 0}

        synced_apps: List[str] = []
        total_duration = 0
        latest_checkpoint = checkpoint

        for session in sessions:
            payload = {
                "device": "mobile",
                "app": normalize_app_name(session.app),
                "timestamp": session.end_time.isoformat(),
                "duration": session.duration_seconds,
            }
            response = requests.post(f"{self.backend_api}/ingest", json=payload, timeout=5)
            if response.status_code == 200:
                synced_apps.append(payload["app"])
                total_duration += session.duration_seconds
                latest_checkpoint = session.end_time if not latest_checkpoint or session.end_time > latest_checkpoint else latest_checkpoint

        if latest_checkpoint:
            self._save_checkpoint(latest_checkpoint)

        return {
            "synced": True,
            "sessions": len(sessions),
            "apps": sorted(set(synced_apps)),
            "total_duration": total_duration,
        }

    def run(self) -> None:
        self.running = True
        while self.running:
            try:
                result = self.sync_once()
                if result.get("synced") and result.get("sessions"):
                    logger.info(
                        "[mobile-adb] synced %s sessions across %s apps (%ss)",
                        result["sessions"],
                        len(result.get("apps", [])),
                        result["total_duration"],
                    )
            except Exception:
                pass
            time.sleep(self.poll_interval_seconds)

    def stop(self) -> None:
        self.running = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Android mobile usage statistics via ADB wireless debugging.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--backend-api", default="http://localhost:8000/api")
    args = parser.parse_args()

    daemon = MobileAdbSyncDaemon(backend_api=args.backend_api, config_path=args.config)
    daemon.run()


if __name__ == "__main__":
    main()