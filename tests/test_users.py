# tests/test_users.py
import os
import pytest
from app.database import init_db
from app.models import create_user, get_user_by_email, get_user_by_api_key, update_user_plan

TEST_DB = "./data/test_users.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_create_user_returns_api_key():
    result = create_user(TEST_DB, email="test@example.com", password="securepass123")
    assert "api_key" in result
    assert result["api_key"].startswith("sk_")
    assert result["email"] == "test@example.com"
    assert result["plan"] == "free"


def test_create_user_duplicate_email_fails():
    create_user(TEST_DB, email="test@example.com", password="pass1")
    with pytest.raises(ValueError, match="Email already registered"):
        create_user(TEST_DB, email="test@example.com", password="pass2")


def test_get_user_by_email():
    create_user(TEST_DB, email="find@example.com", password="pass")
    user = get_user_by_email(TEST_DB, "find@example.com")
    assert user is not None
    assert user["email"] == "find@example.com"


def test_get_user_by_email_not_found():
    user = get_user_by_email(TEST_DB, "nobody@example.com")
    assert user is None


def test_get_user_by_api_key():
    result = create_user(TEST_DB, email="key@example.com", password="pass")
    user = get_user_by_api_key(TEST_DB, result["api_key"])
    assert user is not None
    assert user["email"] == "key@example.com"


def test_get_user_by_api_key_not_found():
    user = get_user_by_api_key(TEST_DB, "sk_nonexistent")
    assert user is None


def test_update_user_plan():
    result = create_user(TEST_DB, email="plan@example.com", password="pass")
    update_user_plan(TEST_DB, result["api_key"], plan="pro", stripe_customer_id="cus_123")
    user = get_user_by_api_key(TEST_DB, result["api_key"])
    assert user["plan"] == "pro"
    assert user["stripe_customer_id"] == "cus_123"


def test_password_is_hashed():
    result = create_user(TEST_DB, email="hash@example.com", password="mypassword")
    user = get_user_by_email(TEST_DB, "hash@example.com")
    assert user["password_hash"] != "mypassword"
    assert len(user["password_hash"]) > 20
