# tests/test_stripe_webhook.py
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user, get_user_by_email, update_user_plan

TEST_DB = "./data/test_stripe_webhook.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
@patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB)
def test_webhook_checkout_completed_upgrades_user(mock_construct):
    # Create a user first
    result = create_user(TEST_DB, email="stripe@example.com", password="securepass123")
    update_user_plan(TEST_DB, result["api_key"], stripe_customer_id="cus_test123")

    mock_construct.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_test123",
                "metadata": {"plan": "pro"}
            }
        }
    }

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "test_sig"}
    )
    assert response.status_code == 200

    user = get_user_by_email(TEST_DB, "stripe@example.com")
    assert user["plan"] == "pro"


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
@patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB)
def test_webhook_subscription_deleted_downgrades_user(mock_construct):
    result = create_user(TEST_DB, email="cancel@example.com", password="securepass123")
    update_user_plan(TEST_DB, result["api_key"], plan="pro", stripe_customer_id="cus_cancel")

    mock_construct.return_value = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "customer": "cus_cancel"
            }
        }
    }

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "test_sig"}
    )
    assert response.status_code == 200

    user = get_user_by_email(TEST_DB, "cancel@example.com")
    assert user["plan"] == "free"


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
def test_webhook_unhandled_event(mock_construct):
    mock_construct.return_value = {
        "type": "some.other.event",
        "data": {"object": {}}
    }

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "test_sig"}
    )
    assert response.status_code == 200


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
def test_webhook_invalid_signature(mock_construct):
    mock_construct.side_effect = Exception("Invalid signature")

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "bad_sig"}
    )
    assert response.status_code == 400
