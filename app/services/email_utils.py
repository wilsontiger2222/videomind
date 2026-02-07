# app/services/email_utils.py
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import SENDGRID_API_KEY, ADMIN_EMAIL
from app.logging_config import setup_logging

logger = setup_logging("email")


def send_email(to_email, subject, body, from_email=None):
    """Send an email via SendGrid. Returns status dict."""
    if not SENDGRID_API_KEY:
        logger.warning("No SendGrid API key configured, skipping email")
        return {"status": "skipped", "reason": "No SendGrid API key configured"}

    sender = from_email or "noreply@videomind.ai"

    message = Mail(
        from_email=sender,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent to {to_email}: {subject} (status: {response.status_code})")
        return {"status": "sent", "status_code": response.status_code}
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return {"status": "failed", "error": str(e)}
