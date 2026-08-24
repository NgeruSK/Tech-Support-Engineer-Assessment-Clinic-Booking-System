def test_root_returns_service_info(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "Clinic Booking API"


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
