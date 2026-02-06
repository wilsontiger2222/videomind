import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.auth import APIKeyMiddleware


def create_test_app():
    test_app = FastAPI()
    test_app.add_middleware(APIKeyMiddleware)

    @test_app.get("/api/v1/health")
    def health():
        return {"status": "healthy"}

    @test_app.get("/api/v1/protected")
    def protected():
        return {"data": "secret"}

    return test_app


@pytest.fixture
def client():
    return TestClient(create_test_app())


def test_request_without_api_key_is_rejected(client):
    response = client.get("/api/v1/protected")
    assert response.status_code == 401


def test_request_with_invalid_api_key_is_rejected(client):
    response = client.get(
        "/api/v1/protected",
        headers={"Authorization": "Bearer invalid-key"},
    )
    assert response.status_code == 401


def test_request_with_valid_api_key_passes(client):
    response = client.get(
        "/api/v1/protected",
        headers={"Authorization": "Bearer test-key-123"},
    )
    assert response.status_code == 200


def test_health_endpoint_works_without_key(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
