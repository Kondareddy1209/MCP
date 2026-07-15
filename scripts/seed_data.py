import sys
import os
import random
from datetime import date, timedelta
from sqlmodel import Session, select

# Adjust path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import engine, init_db
from models import Expense, AppUsage, DailyScreenTime, AppClassification, ProductivityMetricsCache

def seed():
    # Initialize DB (creates tables)
    init_db()
    
    with Session(engine) as session:
        # Clear tables
        for tbl in [Expense, AppUsage, DailyScreenTime, AppClassification, ProductivityMetricsCache]:
            records = session.exec(select(tbl)).all()
            for r in records:
                session.delete(r)
        session.commit()
        
        print("Cleared existing database records.")
        
        # 1. Seed Classifications
        classifications = [
            AppClassification(app_name="VS Code", classification="productive"),
            AppClassification(app_name="Cursor", classification="productive"),
            AppClassification(app_name="Terminal", classification="productive"),
            AppClassification(app_name="Chrome", classification="neutral"),
            AppClassification(app_name="YouTube", classification="distracting"),
            AppClassification(app_name="Instagram", classification="distracting"),
            AppClassification(app_name="Slack", classification="neutral"),
            AppClassification(app_name="Netflix", classification="distracting"),
        ]
        for c in classifications:
            session.add(c)
            
        # 2. Seed Expenses
        expenses = [
            Expense(amount=450.0, category="food", description="Swiggy Dinner", date=date.today() - timedelta(days=1)),
            Expense(amount=150.0, category="food", description="Starbucks Coffee", date=date.today() - timedelta(days=2)),
            Expense(amount=699.0, category="subscriptions", description="Netflix Premium", date=date.today() - timedelta(days=4)),
            Expense(amount=199.0, category="subscriptions", description="Spotify Student", date=date.today() - timedelta(days=6)),
            Expense(amount=2500.0, category="utilities", description="Electricity Bill", date=date.today() - timedelta(days=3)),
            Expense(amount=120.0, category="transport", description="Uber ride", date=date.today() - timedelta(days=5)),
            Expense(amount=320.0, category="food", description="Lunch box", date=date.today()),
        ]
        for e in expenses:
            session.add(e)
            
        # 3. Seed App Usage (Last 7 days)
        apps = [
            ("VS Code", "productive"),
            ("Cursor", "productive"),
            ("Terminal", "productive"),
            ("Chrome", "neutral"),
            ("YouTube", "distracting"),
            ("Instagram", "distracting"),
            ("Netflix", "distracting"),
        ]
        
        for i in range(7):
            current_date = date.today() - timedelta(days=i)
            # Add laptop app usage
            for app, cl in apps:
                if cl == "productive":
                    dur = random.randint(3600, 14400)
                elif cl == "distracting":
                    dur = random.randint(1800, 10800)
                else:
                    dur = random.randint(1800, 7200)
                    
                usage = AppUsage(
                    app_name=app,
                    duration_seconds=dur,
                    device="laptop",
                    date=current_date
                )
                session.add(usage)
                
            # Add mobile app usage
            mobile_apps = ["Instagram", "Chrome", "YouTube"]
            for app in mobile_apps:
                dur = random.randint(900, 5400)
                usage = AppUsage(
                    app_name=app,
                    duration_seconds=dur,
                    device="mobile",
                    date=current_date
                )
                session.add(usage)
                
        # 4. Seed Daily Screen Time
        for i in range(7):
            current_date = date.today() - timedelta(days=i)
            laptop_time = random.randint(18000, 28800) # 5-8 hours
            mobile_time = random.randint(7200, 14400)   # 2-4 hours
            
            session.add(DailyScreenTime(total_time_seconds=laptop_time, device="laptop", date=current_date))
            session.add(DailyScreenTime(total_time_seconds=mobile_time, device="mobile", date=current_date))
            
        session.commit()
        print("Successfully seeded mock database with classifications, expenses, app usages, and screen time records!")

if __name__ == "__main__":
    seed()
