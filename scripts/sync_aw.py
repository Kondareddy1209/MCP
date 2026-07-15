import sys
import os
import requests
from datetime import date, datetime, timezone

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AW_API = "http://localhost:5600/api/v1"
BACKEND_API = "http://localhost:8000/api"

def get_window_bucket():
    try:
        r = requests.get(f"{AW_API}/buckets", timeout=3)
        r.raise_for_status()
        buckets = r.json()
        for bucket_id in buckets.keys():
            if "aw-watcher-window" in bucket_id:
                return bucket_id
    except Exception as e:
        print(f"[-] Could not connect to ActivityWatch API: {e}")
        return None

def sync():
    print("[*] Starting ActivityWatch Sync...")
    bucket_id = get_window_bucket()
    if not bucket_id:
        print("[-] ActivityWatch is not running or window watcher bucket was not found.")
        print("[-] Please ensure aw-qt is running locally.")
        return
        
    print(f"[+] Found window bucket: {bucket_id}")
    
    # Query events for today
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    start_iso = today_start.isoformat().replace("+00:00", "Z")
    
    try:
        # Request events starting from today
        url = f"{AW_API}/buckets/{bucket_id}/events"
        params = {"start": start_iso}
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        events = r.json()
    except Exception as e:
        print(f"[-] Error fetching events: {e}")
        return
        
    if not events:
        print("[*] No window events recorded for today.")
        return
        
    print(f"[+] Fetched {len(events)} events for today.")
    
    # Aggregate durations by app_name
    app_durations = {}
    total_screen_time_seconds = 0
    
    for event in events:
        data = event.get("data", {})
        app = data.get("app")
        if not app:
            continue
            
        # duration in aw is in seconds (or fractional seconds)
        duration = float(event.get("duration", 0))
        if duration <= 0:
            continue
            
        app_durations[app] = app_durations.get(app, 0.0) + duration
        total_screen_time_seconds += duration

    # Format into app_usage payloads
    payload = []
    today_str = date.today().isoformat()
    
    for app_name, duration in app_durations.items():
        payload.append({
            "app_name": app_name,
            "duration_seconds": int(duration),
            "device": "laptop",
            "date": today_str
        })
        
    if not payload:
        print("[*] No valid app events to sync.")
        return
        
    # Push app usages
    try:
        r = requests.post(f"{BACKEND_API}/app-usage/bulk", json=payload, timeout=5)
        r.raise_for_status()
        print(f"[+] Successfully synced {len(payload)} app usage stats to backend.")
    except Exception as e:
        print(f"[-] Failed to sync app usage: {e}")
        
    # Push screen time
    screen_time_payload = {
        "total_time_seconds": int(total_screen_time_seconds),
        "device": "laptop",
        "date": today_str
    }
    try:
        r = requests.post(f"{BACKEND_API}/screen-time/", json=screen_time_payload, timeout=5)
        r.raise_for_status()
        print(f"[+] Successfully synced total laptop screen time: {int(total_screen_time_seconds)} seconds.")
    except Exception as e:
        print(f"[-] Failed to sync laptop screen time: {e}")

if __name__ == "__main__":
    sync()
