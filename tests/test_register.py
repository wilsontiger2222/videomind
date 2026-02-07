# tests/test_register.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

TEST_DB = "./data/test_register.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_register_returns_api_key():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "new@example.com", "password": "securepass123"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["api_key"].startswith("sk_")
    assert data["email"] == "new@example.com"
    assert data["plan"] == "free"


def test_register_duplicate_email():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        client.post("/api/v1/register", json={"email": "dup@example.com", "password": "pass1pass1"})
        response = client.post("/api/v1/register", json={"email": "dup@example.com", "password": "pass2pass2"})
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_register_missing_fields():
    response = client.post("/api/v1/register", json={"email": "no@pass.com"})
    assert response.status_code == 422


def test_register_short_password():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "short@example.com", "password": "12345"}
        )
    assert response.status_code == 400
    assert "at least 8 characters" in response.json()["detail"]
