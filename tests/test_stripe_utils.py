# tests/test_stripe_utils.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.stripe_utils import create_stripe_customer, create_checkout_session


@patch("app.services.stripe_utils.stripe.Customer.create")
def test_create_stripe_customer(mock_create):
    mock_create.return_value = MagicMock(id="cus_test123")

    customer_id = create_stripe_customer("user@example.com")

    assert customer_id == "cus_test123"
    mock_create.assert_called_once_with(email="user@example.com")


@patch("app.services.stripe_utils.stripe.checkout.Session.create")
def test_create_checkout_session_pro(mock_create):
    mock_create.return_value = MagicMock(url="https://checkout.stripe.com/session123")

    url = create_checkout_session("cus_test123", "pro")

    assert url == "https://checkout.stripe.com/session123"
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["customer"] == "cus_test123"
    assert call_kwargs["mode"] == "subscription"


@patch("app.services.stripe_utils.stripe.checkout.Session.create")
def test_create_checkout_session_business(mock_create):
    mock_create.return_value = MagicMock(url="https://checkout.stripe.com/biz456")

    url = create_checkout_session("cus_test123", "business")

    assert url == "https://checkout.stripe.com/biz456"


def test_create_checkout_session_invalid_plan():
    with pytest.raises(ValueError, match="Invalid plan"):
        create_checkout_session("cus_test123", "enterprise")
