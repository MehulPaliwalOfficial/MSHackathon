from fastapi.testclient import TestClient

from app.api import create_app
from app.database import Database


def test_health_endpoint(tmp_path):
    app = create_app(Database(tmp_path / "api.sqlite3"))
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_endpoint_plans_trip(tmp_path):
    app = create_app(Database(tmp_path / "api2.sqlite3"))
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        headers={"X-User-ID": "api-user"},
        json={"message": "Plan 8 days in Japan under ₹1.5 lakh for two people. We love food, culture and nature."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["trip"]["itinerary"]["destination"] == "Japan"
    assert len(data["trip"]["itinerary"]["days"]) == 8


def test_modify_endpoint(tmp_path):
    app = create_app(Database(tmp_path / "api3.sqlite3"))
    client = TestClient(app)
    first = client.post(
        "/api/chat",
        headers={"X-User-ID": "api-user"},
        json={"message": "Plan 5 days in France for two people with museums and food"},
    ).json()
    trip_id = first["trip"]["id"]
    response = client.post(
        f"/api/trips/{trip_id}/modify",
        headers={"X-User-ID": "api-user"},
        json={"instruction": "Remove museums"},
    )
    assert response.status_code == 200
    assert response.json()["trip"]["version"] == 2
