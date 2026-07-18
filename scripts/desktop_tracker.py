import time
import requests
import ctypes
import os
import sys
import uuid
import threading
import json
from datetime import date, datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def get_ist_time() -> datetime:
    return datetime.now(IST)


# Adjust path to import backend classification module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



# Conditional imports for Windows
try:
    import win32gui
    import win32process
    import win32api
    import psutil
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

class InputDensityTracker:
    def __init__(self):
        self.input_count = 0
        self.last_mouse_pos = None
        self.lock = threading.Lock()
        self.running = False
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._poll_inputs, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        
    def get_and_reset_count(self) -> int:
        with self.lock:
            count = self.input_count
            self.input_count = 0
            return count

    def _poll_inputs(self):
        while self.running:
            try:
                # 1. Track Mouse Movement
                pos = win32api.GetCursorPos()
                if self.last_mouse_pos is None:
                    self.last_mouse_pos = pos
                elif pos != self.last_mouse_pos:
                    with self.lock:
                        self.input_count += 1
                    self.last_mouse_pos = pos
            except Exception:
                pass
                
            try:
                # 2. Track Mouse Buttons (Left, Right)
                for key in [0x01, 0x02]:
                    if win32api.GetAsyncKeyState(key) != 0:
                        with self.lock:
                            self.input_count += 1
            except Exception:
                pass
                
            try:
                # 3. Track Keyboard Keys (common virtual key ranges: Backspace to Z)
                for key in range(0x08, 0x5B):
                    if win32api.GetAsyncKeyState(key) != 0:
                        with self.lock:
                            self.input_count += 1
            except Exception:
                pass
                
            time.sleep(0.1)  # Poll inputs every 100ms

def get_active_window_details():
    if not IS_WINDOWS:
        return "Non-Windows OS", "No active window", ""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return "Idle", "System idle", ""
            
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid)
        app_name = process.name().replace(".exe", "")
        
        # Mapping
        mapping = {
            "chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox",
            "code": "VS Code", "cursor": "Cursor", "slack": "Slack",
            "explorer": "File Explorer", "pycharm64": "PyCharm"
        }
        app_name = mapping.get(app_name.lower(), app_name.capitalize())
        
        window_title = win32gui.GetWindowText(hwnd)
        return app_name, window_title, ""
    except Exception:
        return "Unknown", "Unknown Process", ""

class ItsYouTracker:
    def __init__(self, api_url: str = "http://localhost:8000/api", poll_interval: float = 1.0):
        self.api_url = api_url
        self.poll_interval = poll_interval  # check active app state every 1 second
        
        self.input_tracker = InputDensityTracker()
        
        # Adaptive states
        self.rolling_avg_score = 15.0  # Initial baseline inputs/minute
        self.session_id = str(uuid.uuid4())
        self.current_app = None
        self.current_title = None
        self.app_start_time = time.time()
        
        # Idle/Session state
        self.last_activity_time = time.time()
        self.is_idle = False
        self.accumulated_active_seconds_today = 0
        
        # Buffer
        self.minute_input_sum = 0
        self.minute_start_time = time.time()
        
        # Debouncing transient switches
        self.pending_app = None
        self.pending_title = None
        self.pending_since = 0

        # Reliability properties (Task 11)
        self.retry_queue = []
        self.last_heartbeat_time = time.time()
        self.paused = False

        
    def post_event(self, event_type: str, app_name: str = None, title: str = None, meta: dict = None):
        """Sends a raw event to the FastAPI event-driven endpoint."""
        ist_now = get_ist_time()
        url = f"{self.api_url}/events/"
        payload = {
            "event_type": event_type,
            "timestamp": ist_now.isoformat(),
            "app_name": app_name,
            "window_title": title,
            "metadata_json": json.dumps(meta) if meta else None
        }
        try:
            r = requests.post(url, json=payload, timeout=2)
            if r.status_code != 200:
                print(f"[-] Event upload failed: {r.text}, buffering offline...")
                self.retry_queue.append((url, payload))
            else:
                self._flush_retry_queue()
        except Exception as e:
            print(f"[-] Network error posting event: {e}, buffering offline...")
            self.retry_queue.append((url, payload))

    def post_app_usage(self, app_name: str, duration: int, input_events: int, activity_score: float, idle: bool):
        """Posts an aggregated minute/app-switch usage block to backend."""
        ist_now = get_ist_time()
        url = f"{self.api_url}/app-usage/"
        payload = {
            "app_name": app_name,
            "duration_seconds": duration,
            "device": "laptop",
            "date": ist_now.date().isoformat(),
            "timestamp": ist_now.isoformat(),
            "session_id": self.session_id,
            "activity_score": activity_score,
            "input_events": input_events,
            "idle_flag": idle,
            "device_type": "desktop"
        }
        try:
            r = requests.post(url, json=payload, timeout=2)
            if r.status_code == 200:
                print(f"[+] Aggregation: {app_name} | {duration}s | Score: {round(activity_score, 1)} | Idle: {idle}")
                self._flush_retry_queue()
            else:
                print(f"[-] Failed to upload usage: {r.text}, buffering offline...")
                self.retry_queue.append((url, payload))
        except Exception as e:
            print(f"[-] Network error posting usage: {e}, buffering offline...")
            self.retry_queue.append((url, payload))

    def _flush_retry_queue(self):
        """Flushes offline-buffered payloads in order (Task 11)"""
        if not self.retry_queue:
            return
        print(f"[Tracker] Attempting to flush {len(self.retry_queue)} buffered offline payloads...")
        flushed = []
        for item in list(self.retry_queue):
            url, payload = item
            try:
                r = requests.post(url, json=payload, timeout=2)
                if r.status_code == 200:
                    flushed.append(item)
                else:
                    break  # Stop to preserve sequence order
            except Exception:
                break
        for item in flushed:
            self.retry_queue.remove(item)

    def classify_state(self, app_name: str, score: float) -> str:
        """Classifies state dynamically based on rolling average."""
        threshold = max(2.0, self.rolling_avg_score * 0.5)
        
        # Import classification logic locally to inspect rules
        from classification import auto_classify
        app_class = auto_classify(app_name)
        
        if score < threshold:
            return "passive"
        
        if app_class == "productive":
            return "deep_active" if score > self.rolling_avg_score else "light_active"
        elif app_class == "neutral":
            return "light_active"
        else:
            return "passive"

    def run(self):
        if not IS_WINDOWS:
            print("[-] Desktop Tracker requires Windows pywin32 API.")
            sys.exit(1)
            
        print(f"[+] Starting it'syou Event-Driven Tracker (Session Mode)...")
        print(f"[+] Session ID: {self.session_id}")
        
        # Recover unfinished session (Task 11)
        try:
            r = requests.get(f"{self.api_url}/last-active-app", timeout=2)
            if r.status_code == 200:
                last = r.json()
                if last and last.get("status") == "active":
                    last_app = last.get("app")
                    last_window = last.get("window")
                    print(f"[Tracker] Recovered unfinished session for '{last_app}'. Closing it cleanly.")
                    # Close it with a blur event
                    self.post_event("blur", last_app, last_window)
        except Exception as e:
            print(f"[Tracker] Unfinished session recovery query warning: {e}")

        self.input_tracker.start()
        
        # Fire initial SESSION_START
        self.post_event("SESSION_START", meta={"session_id": self.session_id})
        
        self.current_app, self.current_title, _ = get_active_window_details()
        # Post initial focus event
        self.post_event("focus", self.current_app, self.current_title)
        self.post_event("APP_SWITCH", self.current_app, self.current_title, {"previous_app": None})
        self.app_start_time = time.time()
        self.last_heartbeat_time = time.time()
        
        try:
            while True:
                if getattr(self, "paused", False):
                    time.sleep(1.0)
                    continue

                # Heartbeat check (Task 11)
                if time.time() - self.last_heartbeat_time >= 30.0:
                    self.post_event("heartbeat", "ItsYouTrackerDaemon", "Active and running")
                    self.last_heartbeat_time = time.time()

                # 1. Fetch inputs gathered during the interval
                inputs_in_interval = self.input_tracker.get_and_reset_count()
                self.minute_input_sum += inputs_in_interval
                
                # Check active window details
                app_name, title, _ = get_active_window_details()
                
                # Ignore tracker-related processes (Phase 1)
                ignored_apps = ["tracker", "itsyoutrackerdaemon", "python", "uvicorn", "cmd", "powershell", "py", "unknown"]
                if app_name.lower().strip() in ignored_apps:
                    if self.current_app:
                        app_name = self.current_app
                        title = self.current_title
                    else:
                        app_name = "Idle"
                        title = "System standby"
                
                # Register activity timestamps
                if inputs_in_interval > 0:
                    self.last_activity_time = time.time()
                    if self.is_idle:
                        # Resume session
                        self.is_idle = False
                        self.post_event("IDLE_END", app_name, title)
                        # Post focus on resume
                        self.post_event("focus", app_name, title)
                        self.app_start_time = time.time()
                        print("[+] System resumed from idle.")
                
                # 2. Check Idle/Inactivity state (STEP 3: 60 seconds threshold)
                time_since_input = time.time() - self.last_activity_time
                if time_since_input >= 60:
                    if not self.is_idle:
                        self.is_idle = True
                        # Post blur on idle start
                        if self.current_app:
                            # STEP 2: ON blur(app): store duration in app_usage
                            duration = int(time.time() - self.app_start_time - time_since_input)
                            if duration > 0:
                                self.post_app_usage(self.current_app, duration, self.minute_input_sum, 0.0, True)
                            self.post_event("blur", self.current_app, self.current_title)
                        
                        # STEP 3: Insert SYSTEM_IDLE event
                        self.post_event("idle", "SYSTEM_IDLE", "No user activity detected")
                        print("[-] System idle triggered (> 60s inactivity).")
                        
                        # End current session
                        self.post_event("SESSION_END", meta={"session_id": self.session_id, "duration": time.time() - self.app_start_time})
                        
                        self.current_app = None
                        self.minute_input_sum = 0
                        
                    # Sleep and wait
                    time.sleep(1.0)
                    continue
                    
                # If was idle but now active, start new session
                if self.current_app is None and not self.is_idle:
                    self.session_id = str(uuid.uuid4())
                    self.post_event("SESSION_START", meta={"session_id": self.session_id})
                    print(f"[+] Re-established Session: {self.session_id}")
                    self.current_app = app_name
                    self.current_title = title
                    self.app_start_time = time.time()
                    self.post_event("focus", app_name, title)
                    self.post_event("APP_SWITCH", app_name, title, {"previous_app": "Idle"})
                    
                # 3. Check App Switching with Debouncing (2.0s sustained threshold)
                if app_name != self.current_app or title != self.current_title:
                    if app_name != self.pending_app or title != self.pending_title:
                        self.pending_app = app_name
                        self.pending_title = title
                        self.pending_since = time.time()
                    else:
                        time_sustained = time.time() - self.pending_since
                        if time_sustained >= 2.0:
                            duration = int(time.time() - self.app_start_time - time_sustained)
                            if self.current_app and duration > 0:
                                # Calculate current activity score for this app period
                                mins = max(0.1, duration / 60.0)
                                score = self.minute_input_sum / mins
                                
                                # STEP 2: ON blur(app): store duration in app_usage
                                self.post_app_usage(self.current_app, duration, self.minute_input_sum, score, self.is_idle)
                                
                                # Update rolling average if active
                                if not self.is_idle and self.minute_input_sum > 0:
                                    self.rolling_avg_score = (self.rolling_avg_score * 4 + score) / 5.0
                            
                            # Post focus and blur events
                            if self.current_app:
                                self.post_event("blur", self.current_app, self.current_title)
                            self.post_event("focus", app_name, title)
                            
                            # Fire APP_SWITCH event
                            self.post_event("APP_SWITCH", app_name, title, {"previous_app": self.current_app, "duration": duration})
                            
                            self.current_app = app_name
                            self.current_title = title
                            self.app_start_time = self.pending_since
                            self.minute_input_sum = 0
                            self.pending_app = None
                            self.pending_title = None
                else:
                    self.pending_app = None
                    self.pending_title = None
                    
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print("\n[*] Shutting down Windows desktop tracker daemon...")
            self.input_tracker.stop()
            # Post final blur and app usage before exit
            if self.current_app:
                duration = int(time.time() - self.app_start_time)
                if duration > 0:
                    self.post_app_usage(self.current_app, duration, self.minute_input_sum, 0.0, False)
                self.post_event("blur", self.current_app, self.current_title)
            self.post_event("SESSION_END", meta={"session_id": self.session_id, "reason": "user_exit"})
                    
if __name__ == "__main__":
    import ctypes
    # Win32 Mutex to ensure single tracker instance (Task 11)
    MUTEX_NAME = "Global\\ItsYouTrackerMutex"
    try:
        kernel32 = ctypes.windll.kernel32
        mutex_handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            print("[-] Another instance of ItsYouTracker is already running. Exiting...")
            sys.exit(0)
    except Exception as e:
        print(f"[!] Mutex warning: {e}")

    api = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/api"
    tracker = ItsYouTracker(api_url=api)
    tracker.run()
