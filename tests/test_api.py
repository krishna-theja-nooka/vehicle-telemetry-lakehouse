from fastapi.testclient import TestClient

from fleet.api import create_app


def test_health_and_no_data(paths):
    client = TestClient(create_app(paths))
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 503
    assert client.get("/api/overview").status_code == 503
    assert client.get("/").status_code == 200


def test_snapshot_metrics_and_trace(client):
    response = client.get("/api/overview")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["vehicles"] == 1
    assert summary["kwh_per_100km"] == 20
    assert summary["cost_usd"] == 8
    assert response.headers["X-Request-ID"]
    assert client.get("/ready").status_code == 200


def test_region_is_bounded_and_parameterized(client):
    assert client.get("/api/overview?region=Austin").json()["summary"]["vehicles"] == 1
    assert client.get("/api/overview?region=Denver").json()["summary"]["vehicles"] == 0
    assert client.get("/api/overview", params={"region": "Austin' OR 1=1--"}).status_code == 422


def test_vehicle_lookup_and_unknown_vehicle(client):
    assert len(client.get("/api/vehicles/EV-001/trips").json()["trips"]) == 1
    assert client.get("/api/vehicles/EV-999/trips").status_code == 404
    assert client.get("/api/vehicles/invalid/trips").status_code == 422


def test_read_only_surface(client):
    assert client.post("/api/overview", json={"sql": "DROP TABLE mart_fleet"}).status_code == 405
    assert client.get("/api/overview").status_code == 200


def test_invalid_pointer_fails_closed(paths):
    paths.serving.mkdir(parents=True)
    (paths.serving / "CURRENT").write_text("../../secret")
    assert TestClient(create_app(paths)).get("/ready").status_code == 503
