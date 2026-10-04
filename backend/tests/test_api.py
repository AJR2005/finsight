from .conftest import SAMPLE


def test_requires_auth(client):
    assert client.get("/api/dashboard").status_code == 401


def test_login_flow(client):
    client.post("/api/auth/register", json={"name": "A", "email": "a@test.com", "password": "secret123"})
    assert client.post("/api/auth/login", data={"username": "a@test.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", data={"username": "A@test.com", "password": "secret123"}).status_code == 200


def test_import_is_idempotent_and_categorised(client, auth):
    files = {"file": ("hdfc.csv", SAMPLE.read_bytes(), "text/csv")}
    first = client.post("/api/transactions/import", files=files, headers=auth).json()
    assert first["imported"] == 19
    again = client.post("/api/transactions/import", files=files, headers=auth).json()
    assert again["imported"] == 0 and again["duplicates"] == 19

    items = client.get("/api/transactions?limit=100", headers=auth).json()["items"]
    by_desc = {i["description"]: i["category"] for i in items}
    assert by_desc["UPI-NETFLIX COM-netflix@hdfcbank-HDFC0000001-625012345679-NETFLIX"] == "Subscriptions"


def test_correction_applies_to_similar(client, auth):
    for d, ref in (("2026-09-01", 1), ("2026-09-08", 2)):
        client.post("/api/transactions", headers=auth,
                    json={"date": d, "description": f"UPI/{ref}/MOHAN PANIPURI/mohan@ybl", "amount": -60})
    items = client.get("/api/transactions", headers=auth).json()["items"]
    r = client.patch(f"/api/transactions/{items[0]['id']}/category", headers=auth,
                     json={"category": "Food & Dining", "apply_to_similar": True})
    assert r.status_code == 200
    cats = {i["category"] for i in client.get("/api/transactions", headers=auth).json()["items"]}
    assert cats == {"Food & Dining"}


def test_users_cannot_see_each_other(client, auth):
    client.post("/api/transactions", headers=auth, json={"date": "2026-09-01", "description": "X", "amount": -1})
    tid = client.get("/api/transactions", headers=auth).json()["items"][0]["id"]
    other = client.post("/api/auth/register", json={"name": "B", "email": "b@test.com", "password": "secret123"})
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get("/api/transactions", headers=h2).json()["total"] == 0
    assert client.delete(f"/api/transactions/{tid}", headers=h2).status_code == 404


def test_dashboard_insights_and_goals(client, auth):
    client.post("/api/transactions/import", files={"file": ("h.csv", SAMPLE.read_bytes(), "text/csv")}, headers=auth)
    for path in ("/api/dashboard", "/api/insights/forecast", "/api/insights/anomalies",
                 "/api/insights/subscriptions", "/api/investments", "/api/model/metrics"):
        assert client.get(path, headers=auth).status_code == 200, path
    goal = {"name": "Trip", "target_amount": 200000, "target_date": "2028-01-01",
            "current_savings": 20000, "monthly_contribution": 8000}
    assert client.post("/api/goals", json=goal, headers=auth).status_code == 200
    sim = client.post("/api/goals/simulate", json=goal, headers=auth).json()
    assert 0 <= sim["probability"] <= 100 and sim["fan"]
