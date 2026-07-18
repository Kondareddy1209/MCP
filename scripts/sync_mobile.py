import sys
import os
import csv
import argparse
import requests
from datetime import datetime, date

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_API = "http://localhost:8000/api"

def sync_mobile_csv(csv_path: str, dry_run: bool = False):
    print(f"[*] Starting Mobile Data Sync from: {csv_path}")
    if dry_run:
        print("[*] Running in DRY-RUN mode. No changes will be posted to the server.")

    if not os.path.exists(csv_path):
        print(f"[-] CSV file not found at: {csv_path}")
        sys.exit(1)

    # 1. Fetch existing mobile usages to prevent duplicates
    try:
        r = requests.get(f"{BACKEND_API}/app-usage/", timeout=5)
        r.raise_for_status()
        existing_usages = r.json()
        # Create unique key set for existing mobile data
        # Deduplicate on (app_name, date) for mobile daily summaries
        existing_keys = {
            (u["app_name"].lower().strip(), u["date"])
            for u in existing_usages
            if u.get("device") == "mobile"
        }
        print(f"[+] Loaded {len(existing_keys)} existing mobile usage records for deduplication.")
    except Exception as e:
        print(f"[-] Failed to fetch existing records for deduplication: {e}")
        print("[*] Proceeding without remote deduplication check.")
        existing_keys = set()

    # 2. Read and parse CSV file
    parsed_rows = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        # Auto-detect dialect or use dictreader
        reader = csv.DictReader(f)
        
        # Verify column existence
        headers = reader.fieldnames
        if not headers:
            print("[-] CSV headers are empty or file is invalid.")
            sys.exit(1)
            
        print(f"[+] Detected CSV headers: {headers}")
        
        # Map header variations
        pkg_col = next((h for h in headers if "package" in h.lower()), None)
        app_col = next((h for h in headers if "app" in h.lower()), None)
        date_col = next((h for h in headers if "date" in h.lower()), None)
        dur_col = next((h for h in headers if "duration" in h.lower()), None)
        
        if not app_col or not date_col or not dur_col:
            print("[-] Required columns not found. Ensure columns 'App Name', 'Date', and 'Duration' exist.")
            sys.exit(1)
            
        for row_idx, row in enumerate(reader, start=1):
            app_raw = row[app_col]
            package_raw = row[pkg_col] if pkg_col else ""
            date_raw = row[date_col]
            dur_raw = row[dur_col]
            
            if not app_raw or not date_raw or not dur_raw:
                continue
                
            # Use package name if app name is empty, or normalize
            app_name = app_raw.strip() or package_raw.strip()
            if not app_name:
                continue
                
            # Parse date and format to YYYY-MM-DD
            try:
                # Support various formats: YYYY-MM-DD, MM/DD/YYYY, etc.
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
                    try:
                        parsed_date = datetime.strptime(date_raw.strip(), fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    print(f"[!] Row {row_idx}: Could not parse date format '{date_raw}'. Skipping.")
                    continue
            except Exception as e:
                print(f"[!] Row {row_idx}: Date parsing error: {e}. Skipping.")
                continue
                
            # Parse duration in seconds
            try:
                # If formatted as HH:MM:SS or MM:SS
                if ":" in dur_raw:
                    parts = list(map(int, dur_raw.split(":")))
                    if len(parts) == 3:
                        duration_sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
                    elif len(parts) == 2:
                        duration_sec = parts[0] * 60 + parts[1]
                    else:
                        duration_sec = 0
                else:
                    duration_sec = int(float(dur_raw.strip()))
            except Exception as e:
                print(f"[!] Row {row_idx}: Duration parsing error: {e}. Skipping.")
                continue
                
            if duration_sec <= 0:
                continue
                
            parsed_rows.append({
                "app": app_name,
                "date": str(parsed_date),
                "duration": duration_sec,
                # Midnight IST representation for back-compatibility syncs
                "timestamp": f"{parsed_date}T00:00:00+05:30"
            })

    # 3. Synchronize rows
    inserted_count = 0
    skipped_count = 0
    
    for row in parsed_rows:
        key = (row["app"].lower().strip(), row["date"])
        
        # Deduplication check
        if key in existing_keys:
            skipped_count += 1
            continue
            
        if dry_run:
            print(f"[Dry-run] Would ingest: App='{row['app']}', Date={row['date']}, Duration={row['duration']}s")
            inserted_count += 1
        else:
            payload = {
                "device": "mobile",
                "app": row["app"],
                "timestamp": row["timestamp"],
                "duration": row["duration"]
            }
            try:
                r = requests.post(f"{BACKEND_API}/ingest", json=payload, timeout=3)
                if r.status_code == 200:
                    inserted_count += 1
                else:
                    print(f"[!] Failed to ingest {row['app']} for {row['date']}: {r.status_code}")
            except Exception as e:
                print(f"[!] Ingestion connection error for {row['app']}: {e}")
                
    print(f"[*] Sync completed.")
    print(f"[+] Total records parsed: {len(parsed_rows)}")
    print(f"[+] Successfully synced  : {inserted_count}")
    print(f"[+] Skipped (Duplicates) : {skipped_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize Android mobile app usage statistics from CSV export.")
    parser.add_argument("csv_path", help="Path to exported CSV file.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to backend.")
    args = parser.parse_args()
    
    sync_mobile_csv(args.csv_path, dry_run=args.dry_run)
