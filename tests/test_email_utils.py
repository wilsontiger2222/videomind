# tests/test_email_utils.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.email_utils import send_email


@patch("app.services.email_utils.SENDGRID_API_KEY", "test-key")
@patch("app.services.email_utils.SendGridAPIClient")
def test_send_email_success(mock_sg_class):
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=202)
    mock_client.send.return_value = mock_response
    mock_sg_class.return_value = mock_client

    result = send_email(
        to_email="user@example.com",
        subject="Test Subject",
        body="Test body content"
    )

    assert result["status"] == "sent"
    assert result["status_code"] == 202
    mock_client.send.assert_called_once()


@patch("app.services.email_utils.SENDGRID_API_KEY", "test-key")
@patch("app.services.email_utils.SendGridAPIClient")
def test_send_email_failure(mock_sg_class):
    mock_client = MagicMock()
    mock_client.send.side_effect = Exception("API error")
    mock_sg_class.return_value = mock_client

    result = send_email(
        to_email="user@example.com",
        subject="Test Subject",
        body="Test body content"
    )

    assert result["status"] == "failed"
    assert "API error" in result["error"]


@patch("app.services.email_utils.SENDGRID_API_KEY", "")
def test_send_email_no_api_key():
    result = send_email(
        to_email="user@example.com",
        subject="Test",
        body="Body"
    )
    assert result["status"] == "skipped"
    assert "No SendGrid API key" in result["reason"]
