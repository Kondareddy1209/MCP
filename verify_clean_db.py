import sqlite3, os

print("\n=== DB FILES IN PROJECT ===")
for f in os.listdir("."):
    if f.endswith(".db"):
        size = os.path.getsize(f)
        print(f"  {f}  ({size} bytes)")

print("\n=== itsyou_clean.db SCHEMA ===")
conn = sqlite3.connect("itsyou_clean.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print("  Tables:", [t[0] for t in tables])

for table_name in [t[0] for t in tables]:
    c.execute(f"SELECT COUNT(*) FROM [{table_name}]")
    count = c.fetchone()[0]
    print(f"  {table_name}: {count} rows")

conn.close()
print("\nDONE - verification complete")
