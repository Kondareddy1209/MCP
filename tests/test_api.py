from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
import pytest
import os
import sys

# Adjust path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from db import get_session

DATABASE_URL = "sqlite:///test_antigravity.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Override db session dependency to use test database
def override_get_session():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session

@pytest.fixture(name="session", scope="module", autouse=True)
def session_fixture():
    # Setup: create all tables
    SQLModel.metadata.create_all(engine)
    yield
    # Teardown: drop all tables and remove database file
    SQLModel.metadata.drop_all(engine)
    engine.dispose()
    if os.path.exists("test_antigravity.db"):
        try:
            os.remove("test_antigravity.db")
        except PermissionError:
            pass


client = TestClient(app)

def test_create_and_get_expense():
    # Test Expense insertion
    payload = {
        "amount": 299.0,
        "category": "subscriptions",
        "description": "Cursor Pro",
        "date": "2026-07-13"
    }
    response = client.post("/api/expenses/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 299.0
    assert data["category"] == "subscriptions"
    assert data["id"] is not None
    
    # Test retrieve
    get_response = client.get("/api/expenses/")
    assert get_response.status_code == 200
    expenses = get_response.json()
    assert len(expenses) >= 1
    assert expenses[0]["description"] == "Cursor Pro"

def test_delete_expense():
    # Insert one to delete
    payload = {
        "amount": 50.0,
        "category": "food",
        "description": "Snack",
        "date": "2026-07-13"
    }
    response = client.post("/api/expenses/", json=payload)
    data = response.json()
    expense_id = data["id"]
    
    # Delete it
    del_response = client.delete(f"/api/expenses/{expense_id}")
    assert del_response.status_code == 200
    assert del_response.json()["message"] == "Expense deleted successfully"
    
    # Try deleting again (should fail)
    del_again = client.delete(f"/api/expenses/{expense_id}")
    assert del_again.status_code == 404

def test_app_usage_bulk():
    payload = [
        {"app_name": "VS Code", "duration_seconds": 3600, "device": "laptop", "date": "2026-07-13"},
        {"app_name": "YouTube", "duration_seconds": 1800, "device": "laptop", "date": "2026-07-13"}
    ]
    response = client.post("/api/app-usage/bulk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["app_name"] == "VS Code"

def test_upsert_screen_time():
    payload = {
        "total_time_seconds": 7200,
        "device": "laptop",
        "date": "2026-07-13"
    }
    response = client.post("/api/screen-time/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_time_seconds"] == 7200
    
    # Update it
    payload["total_time_seconds"] = 9000
    update_response = client.post("/api/screen-time/", json=payload)
    assert update_response.status_code == 200
    updated_data = update_response.json()
    assert updated_data["total_time_seconds"] == 9000
    assert updated_data["id"] == data["id"]

def test_classification():
    payload = {
        "app_name": "VS Code",
        "classification": "productive"
    }
    response = client.post("/api/classifications/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "VS Code"
    assert data["classification"] == "productive"

def test_analytics():
    response = client.get("/api/analytics/?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "productivity_score" in data
    assert "total_spent" in data
    assert "distraction_cost" in data
    assert "insights" in data

def test_usage_event_ingestion():
    payload = {
        "event_type": "APP_SWITCH",
        "app_name": "Cursor",
        "window_title": "editing analytics.py",
        "metadata_json": "{\"previous_app\": \"Chrome\"}"
    }
    response = client.post("/api/events/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "APP_SWITCH"
    assert data["app_name"] == "Cursor"
    
    # Get events
    get_res = client.get("/api/events/")
    assert get_res.status_code == 200
    events = get_res.json()
    assert len(events) >= 1
    assert events[0]["app_name"] == "Cursor"

def test_app_usage_extended_fields():
    import uuid
    session_id = str(uuid.uuid4())
    payload = {
        "app_name": "VS Code",
        "duration_seconds": 180,
        "device": "laptop",
        "date": "2026-07-14",
        "session_id": session_id,
        "activity_score": 25.5,
        "input_events": 76,
        "idle_flag": False,
        "device_type": "desktop"
    }
    response = client.post("/api/app-usage/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["activity_score"] == 25.5
    assert data["input_events"] == 76
    assert data["idle_flag"] is False
    assert data["device_type"] == "desktop"

def test_ai_dashboard():
    # Test default work type developer
    response = client.get("/api/ai-dashboard?days=7&work_type=developer")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "metrics" in data
    assert "insights" in data
    assert "recommendations" in data
    assert "predictions" in data
    assert "events" in data
    
    # Test work type student simulation
    response_student = client.get("/api/ai-dashboard?days=7&work_type=student")
    assert response_student.status_code == 200
    data_student = response_student.json()
    assert data_student["status"] in ["ONLINE", "SIMULATED"]
    assert "metrics" in data_student

def test_dashboard_aggregate():
    response = client.get("/api/dashboard?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "analytics" in data
    assert "alerts" in data
    assert "events" in data

def test_last_active_app():
    # Insert a dummy event first
    event_payload = {
        "event_type": "focus",
        "app_name": "Chrome",
        "window_title": "YouTube - Ingest Test Video"
    }
    client.post("/api/events/", json=event_payload)

    response = client.get("/api/last-active-app")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Chrome"
    assert data["window"] == "YouTube - Ingest Test Video"
    assert data["status"] == "active"

def test_live_usage():
    # Check that live usage returns summary and events
    response = client.get("/api/live-usage")
    assert response.status_code == 200
    data = response.json()
    assert "last_active" in data
    assert "today_summary" in data
    assert "recent_events" in data

def test_ingest_endpoint():
    ingest_payload = {
        "device": "mobile",
        "app": "Instagram",
        "timestamp": "2026-07-15T12:00:00+05:30",
        "duration": 45
    }
    response = client.post("/api/ingest", json=ingest_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"






