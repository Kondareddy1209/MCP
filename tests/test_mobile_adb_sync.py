import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.mobile_adb_sync import parse_usagestats_output, reconstruct_sessions, MobileAdbSyncDaemon
from services import notification_dispatch


SAMPLE_OUTPUT = """
Usage stats:
  2026-07-18 09:00:00 pkg=com.whatsapp mEventType=move_to_foreground
  2026-07-18 09:14:00 pkg=com.whatsapp mEventType=move_to_background
  2026-07-18 09:15:00 pkg=com.android.chrome mEventType=move_to_foreground
  2026-07-18 09:45:00 pkg=com.android.chrome mEventType=move_to_background
"""


def test_parse_usagestats_output_extracts_events():
    events = parse_usagestats_output(SAMPLE_OUTPUT)
    assert len(events) == 4
    assert events[0]["package"] == "com.whatsapp"
    assert events[0]["event_type"] == "move_to_foreground"


def test_reconstruct_sessions_uses_foreground_background_pairs():
    events = parse_usagestats_output(SAMPLE_OUTPUT)
    sessions = reconstruct_sessions(events)
    assert len(sessions) == 2
    assert sessions[0].app == "com.whatsapp"
    assert sessions[0].duration_seconds == 14 * 60
    assert sessions[1].app == "com.android.chrome"
    assert sessions[1].duration_seconds == 30 * 60


def test_disconnected_device_does_not_crash_or_pollute_state(monkeypatch, tmp_path):
    daemon = MobileAdbSyncDaemon(backend_api="http://localhost:8000/api", config_path=str(tmp_path / "config.json"))
    daemon.host = "192.0.2.10"
    daemon.port = 5555
    daemon.state_path = str(tmp_path / "state.json")

    monkeypatch.setattr("scripts.mobile_adb_sync.adb_connect", lambda host, port: False)

    result = daemon.sync_once()
    assert result["synced"] is False
    assert result["reason"] == "device_unreachable"
    assert not os.path.exists(daemon.state_path)


def test_dispatch_notification_broadcasts_once(monkeypatch):
    calls = []

    async def fake_broadcast(message):
        calls.append(message)

    class FakeManager:
        async def broadcast(self, message):
            await fake_broadcast(message)

    monkeypatch.setattr(notification_dispatch, "_get_push_settings", lambda: {"public_key": "", "private_key": "", "subject": "mailto:test@example.com"})
    monkeypatch.setattr(notification_dispatch, "manager", FakeManager())

    notification_dispatch.dispatch_notification("Burnout Warning", "Take a break.", priority="HIGH", source="intervention")

    assert len(calls) == 1
    assert calls[0]["type"] == "alert"
    assert calls[0]["title"] == "Burnout Warning"
    assert calls[0]["body"] == "Take a break."