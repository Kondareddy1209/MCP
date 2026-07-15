import sqlite3

for db_name in ["itsyou.db", "antigravity.db", "database.db"]:
    print(f"\n{'='*60}")
    print(f"DATABASE: {db_name}")
    print('='*60)
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        print(f"  Tables: {[t[0] for t in tables]}")
        if any(t[0] == 'app_usage' for t in tables):
            c.execute("SELECT COUNT(*) FROM app_usage")
            total = c.fetchone()[0]
            print(f"  app_usage total rows: {total}")
            c.execute("SELECT app_name, date, timestamp FROM app_usage ORDER BY id DESC LIMIT 5")
            rows = c.fetchall()
            print(f"  Last 5 rows:")
            for row in rows:
                print(f"    app={row[0]:<22} date={row[1]!r:<14} timestamp={row[2]!r}")
            c.execute("SELECT DISTINCT date FROM app_usage ORDER BY date DESC LIMIT 10")
            dates = c.fetchall()
            print(f"  Distinct dates (latest 10): {[d[0] for d in dates]}")
        conn.close()
    except Exception as e:
        print(f"  ERROR: {e}")
