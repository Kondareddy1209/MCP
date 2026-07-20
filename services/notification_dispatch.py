"""Shared notification dispatch for websocket alerts and optional Web Push."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from db import engine
from sqlmodel import Session

try:
    from pywebpush import webpush
except Exception:
    webpush = None

try:
    from ws_manager import manager
except Exception:
    manager = None

STATE_FILE = Path("push_state.json")


def _load_runtime_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as handle:
                cfg = json.load(handle)
        except Exception:
            cfg = {}
    if os.path.exists("vapid_keys.json"):
        try:
            with open("vapid_keys.json", "r", encoding="utf-8") as handle:
                vapid_cfg = json.load(handle)
            if isinstance(vapid_cfg, dict):
                cfg.setdefault("push", {})
                cfg["push"].setdefault("public_key", vapid_cfg.get("public_key") or vapid_cfg.get("publicKey") or "")
                cfg["push"].setdefault("private_key", vapid_cfg.get("private_key") or vapid_cfg.get("privateKey") or "")
                cfg["push"].setdefault("subject", vapid_cfg.get("subject") or "mailto:admin@example.com")
        except Exception:
            pass
    return cfg


def _get_push_settings() -> Dict[str, str]:
    cfg = _load_runtime_config().get("push", {})
    return {
        "public_key": os.getenv("VAPID_PUBLIC_KEY") or str(cfg.get("public_key") or ""),
        "private_key": os.getenv("VAPID_PRIVATE_KEY") or str(cfg.get("private_key") or ""),
        "subject": os.getenv("VAPID_SUBJECT") or str(cfg.get("subject") or "mailto:admin@example.com"),
    }


def _safe_json_loads(value: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {"last_alert_fired": {}}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        if isinstance(state, dict):
            state.setdefault("last_alert_fired", {})
            return state
    except Exception:
        pass
    return {"last_alert_fired": {}}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        with STATE_FILE.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
    except Exception:
        pass


def should_send_alert(alert_type: str, cooldown_minutes: int = 30) -> bool:
    state = _load_state()
    last_fired = state.get("last_alert_fired", {}).get(alert_type)
    if not last_fired:
        return True
    try:
        last_dt = datetime.fromisoformat(last_fired)
    except Exception:
        return True
    return (datetime.now(timezone.utc) - last_dt) >= timedelta(minutes=cooldown_minutes)


def mark_alert_sent(alert_type: str) -> None:
    state = _load_state()
    state.setdefault("last_alert_fired", {})[alert_type] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def delete_push_subscription_by_endpoint(endpoint: str) -> None:
    try:
        from crud import delete_push_subscription_by_endpoint as _delete_push_subscription
    except Exception:
        return

    with Session(engine) as session:
        _delete_push_subscription(session, endpoint)


def get_vapid_public_key() -> str:
    return _get_push_settings()["public_key"]


def send_all(payload: Dict[str, Any]) -> None:
    push_settings = _get_push_settings()
    if not push_settings["public_key"] or not push_settings["private_key"] or webpush is None:
        return

    try:
        from crud import get_push_subscriptions
    except Exception:
        return

    with Session(engine) as session:
        for subscription in get_push_subscriptions(session):
            sub_payload = _safe_json_loads(subscription.subscription_json)
            if not sub_payload:
                continue
            try:
                webpush(
                    subscription_info=sub_payload,
                    data=json.dumps(payload),
                    vapid_private_key=push_settings["private_key"],
                    vapid_claims={"sub": push_settings["subject"]},
                )
            except Exception as exc:
                response = getattr(exc, "response", None)
                if getattr(response, "status_code", None) == 410:
                    delete_push_subscription_by_endpoint(subscription.endpoint)
                continue


def dispatch_notification(title: str, body: str, priority: str = "MEDIUM", source: str = "intervention") -> None:
    payload = {
        "type": "alert",
        "title": title,
        "body": body,
        "priority": priority,
        "source": source,
    }

    try:
        if manager is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.broadcast(payload))
            except RuntimeError:
                asyncio.run(manager.broadcast(payload))
    except Exception:
        pass

    try:
        send_all(payload)
    except Exception:
        return