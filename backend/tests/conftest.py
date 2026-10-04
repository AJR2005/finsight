import os
import sys
import tempfile
from pathlib import Path

import pytest

_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["LIVE_PRICES"] = "0"
os.environ["SEED_DEMO"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "hdfc_style_statement.csv"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/auth/register", json={"name": "Test", "email": email, "password": "secret123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
