"""
services/session_engine.py — Session Engine
Translates raw AppUsage and UsageEvent database logs into Pydantic TrackedSession objects.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from models import AppUsage, UsageEvent

class TrackedSession(BaseModel):
    session_id: str
    app_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    input_events: int = 0
    activity_score: float = 0.0
    device: str = "laptop"
    device_type: str = "desktop"
    idle_flag: bool = False
    is_unfinished: bool = False
    window_titles: List[str] = []
    interruptions: int = 0

class SessionEngine:
    @staticmethod
    def reconstruct_sessions(usages: List[AppUsage], events: List[UsageEvent]) -> List[TrackedSession]:
        if not usages:
            return []
            
        # 1. Sort usages chronologically by timestamp
        sorted_usages = sorted(usages, key=lambda u: u.timestamp if u.timestamp else datetime.min)
        
        reconstructed: List[TrackedSession] = []
        
        # 2. Iterate and group consecutive identical usages (same session_id, app_name, and idle_flag)
        for u in sorted_usages:
            if not u.timestamp:
                continue
                
            duration = u.duration_seconds or 0
            start = u.timestamp - timedelta(seconds=duration)
            end = u.timestamp
            idle_state = bool(u.idle_flag or u.app_name == "SYSTEM_IDLE")
            
            # Retrieve window titles matching u.app_name from usage events around the interval
            titles = []
            if events:
                for e in events:
                    if e.timestamp and start - timedelta(seconds=5) <= e.timestamp <= end + timedelta(seconds=5):
                        if e.app_name == u.app_name and e.window_title:
                            titles.append(e.window_title)
            
            # Deduplicate window titles
            seen_titles = []
            for t in titles:
                if t not in seen_titles:
                    seen_titles.append(t)
            
            # Merge consecutive usages with same app_name, same idle_flag, and either same session_id or tiny gap
            if (reconstructed and 
                reconstructed[-1].app_name == u.app_name and 
                reconstructed[-1].idle_flag == idle_state and 
                (reconstructed[-1].session_id == u.session_id or 
                 (start - reconstructed[-1].end_time).total_seconds() < 60)):
                
                last = reconstructed[-1]
                last.end_time = end
                last.duration_seconds += duration
                last.input_events += u.input_events or 0
                
                # Update activity score using weighted duration average
                total_dur = last.duration_seconds
                if total_dur > 0:
                    last.activity_score = ((last.activity_score * (total_dur - duration)) + ((u.activity_score or 0.0) * duration)) / total_dur
                
                # Merge unique window titles
                for t in seen_titles:
                    if t not in last.window_titles:
                        last.window_titles.append(t)
            else:
                reconstructed.append(TrackedSession(
                    session_id=u.session_id or f"session_{len(reconstructed)}",
                    app_name=u.app_name,
                    start_time=start,
                    end_time=end,
                    duration_seconds=duration,
                    input_events=u.input_events or 0,
                    activity_score=u.activity_score or 0.0,
                    device=u.device or "laptop",
                    device_type=u.device_type or "desktop",
                    idle_flag=idle_state,
                    is_unfinished=False,
                    window_titles=seen_titles,
                    interruptions=0
                ))
        
        # 3. Clean jitter by merging consecutive identical focus sessions separated by less than 15s
        final_sessions: List[TrackedSession] = []
        for s in reconstructed:
            if (final_sessions and 
                final_sessions[-1].app_name == s.app_name and 
                final_sessions[-1].idle_flag == s.idle_flag and 
                (s.start_time - final_sessions[-1].end_time).total_seconds() < 15):
                
                last = final_sessions[-1]
                last.end_time = s.end_time
                last.duration_seconds += s.duration_seconds
                last.input_events += s.input_events
                
                # Average activity score
                last.activity_score = (last.activity_score + s.activity_score) / 2.0
                
                # Merge unique titles
                for t in s.window_titles:
                    if t not in last.window_titles:
                        last.window_titles.append(t)
            else:
                final_sessions.append(s)
                
        # 4. Detect unfinished sessions (active in the last 5 minutes)
        # M3 fix: strip tzinfo from both sides so IST-aware stored datetimes
        # don't produce ±5.5h errors when compared against naive datetime.now().
        last_s = final_sessions[-1]
        now_naive = datetime.now()
        last_end_naive = last_s.end_time.replace(tzinfo=None)
        if abs((now_naive - last_end_naive).total_seconds()) < 300:
            last_s.is_unfinished = True
                
        # 5. Calculate interruptions (number of app switch events nested in this session duration)
        for s in final_sessions:
            if events:
                switch_count = sum(1 for e in events if e.event_type == "focus" and s.start_time <= e.timestamp <= s.end_time)
                # Count focus switches as interruptions, subtracting the initial focus setup
                s.interruptions = max(0, switch_count - 1)
                
        return final_sessions
