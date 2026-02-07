# tests/test_e2e_phase3.py
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

TEST_DB = "./data/test_e2e_phase3.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    # Clear rate limit log between tests
    from app.middleware.rate_limit import _request_log
    _request_log.clear()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_full_phase3_user_lifecycle():
    """Test: register -> use API -> check usage -> upgrade via Stripe -> higher limits"""

    # Step 1: Register a new user
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "lifecycle@example.com", "password": "securepass123"}
        )
    assert response.status_code == 200
    api_key = response.json()["api_key"]
    assert api_key.startswith("sk_")

    # Step 2: Check initial usage (free plan)
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {api_key}"}
            )
    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["videos_limit"] == 3

    # Step 3: Simulate Stripe upgrade to pro via webhook
    from app.models import update_user_plan, get_user_by_api_key
    user = get_user_by_api_key(TEST_DB, api_key)
    update_user_plan(TEST_DB, api_key, stripe_customer_id="cus_lifecycle")

    with patch("app.routers.stripe_webhook.stripe.Webhook.construct_event") as mock_construct:
        with patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB):
            mock_construct.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": "cus_lifecycle",
                        "metadata": {"plan": "pro"}
                    }
                }
            }
            response = client.post(
                "/api/v1/stripe/webhook",
                content=b'{}',
                headers={"stripe-signature": "test_sig"}
            )
    assert response.status_code == 200

    # Step 4: Check usage after upgrade (pro plan)
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {api_key}"}
            )
    assert response.status_code == 200
    assert response.json()["plan"] == "pro"
    assert response.json()["videos_limit"] == 30
    assert response.json()["requests_limit"] == 100

    # Step 5: Simulate subscription cancellation
    with patch("app.routers.stripe_webhook.stripe.Webhook.construct_event") as mock_construct:
        with patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB):
            mock_construct.return_value = {
                "type": "customer.subscription.deleted",
                "data": {"object": {"customer": "cus_lifecycle"}}
            }
            response = client.post(
                "/api/v1/stripe/webhook",
                content=b'{}',
                headers={"stripe-signature": "test_sig"}
            )
    assert response.status_code == 200

    # Step 6: Confirm downgrade back to free
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {api_key}"}
            )
    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["videos_limit"] == 3
