"""
DIAGNOSTIC SCRIPT — it'syou Timezone Investigation
Run: python diagnose_timezone.py
Prints exact field formats stored in DB for AppUsage records.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import init_db, get_session
from models import AppUsage
from sqlmodel import select, Session, create_engine
from datetime import date, datetime, timezone
import json

# ─── Init DB ──────────────────────────────────────────────────────────
engine = create_engine("sqlite:///itsyou.db", echo=False)

with Session(engine) as session:
    # ── STEP 1: Sample 5 raw records ──────────────────────────────────
    records = session.exec(select(AppUsage).limit(5)).all()
    print("\n" + "="*60)
    print("STEP 1 — RAW DB RECORDS (first 5)")
    print("="*60)
    for r in records:
        print(f"  id={r.id}  app={r.app_name:<20} date={r.date!r}  timestamp={r.timestamp!r}")

    # ── STEP 2: What is Python date.today()? ─────────────────────────
    today_local = date.today()
    today_utc   = datetime.now(timezone.utc).date()
    print("\n" + "="*60)
    print("STEP 2 — SYSTEM DATE COMPARISON")
    print("="*60)
    print(f"  date.today()          = {today_local}")
    print(f"  datetime.utcnow().date= {datetime.utcnow().date()}")
    print(f"  datetime.now(UTC).date= {today_utc}")

    # ── STEP 3: Filter Test — how many match today? ───────────────────
    today_records = session.exec(
        select(AppUsage).where(AppUsage.date == today_local)
    ).all()
    yesterday = date.fromordinal(today_local.toordinal() - 1)
    yesterday_records = session.exec(
        select(AppUsage).where(AppUsage.date == yesterday)
    ).all()
    all_records = session.exec(select(AppUsage)).all()

    print("\n" + "="*60)
    print("STEP 3 — DATE FILTER TEST")
    print("="*60)
    print(f"  Total records in DB         : {len(all_records)}")
    print(f"  Records where date=today    : {len(today_records)}  (today={today_local})")
    print(f"  Records where date=yesterday: {len(yesterday_records)}  (yesterday={yesterday})")

    # ── STEP 4: Distinct dates in DB ─────────────────────────────────
    dates_in_db = sorted(set(r.date for r in all_records))
    print("\n" + "="*60)
    print("STEP 4 — DISTINCT DATES IN DB")
    print("="*60)
    for d in dates_in_db[-10:]:
        count = sum(1 for r in all_records if r.date == d)
        marker = " ← TODAY" if d == today_local else ""
        print(f"  {d}  ({count} records){marker}")

    # ── STEP 5: Timestamp format detail ──────────────────────────────
    print("\n" + "="*60)
    print("STEP 5 — TIMESTAMP FORMAT DETAIL (first 3 records)")
    print("="*60)
    for r in records[:3]:
        ts = r.timestamp
        ts_type = type(ts).__name__
        has_tzinfo = getattr(ts, 'tzinfo', None) is not None if ts else False
        print(f"  app={r.app_name:<20} timestamp={ts!r}")
        print(f"    type={ts_type}  has_tzinfo={has_tzinfo}")
        if ts:
            print(f"    isoformat={ts.isoformat()}")
            print(f"    UTC midnight today = {datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)}")
        print()

    print("="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)
