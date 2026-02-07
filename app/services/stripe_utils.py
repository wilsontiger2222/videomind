# app/services/stripe_utils.py
import stripe
from app.config import STRIPE_SECRET_KEY, STRIPE_PRO_PRICE_ID, STRIPE_BUSINESS_PRICE_ID

stripe.api_key = STRIPE_SECRET_KEY

PRICE_IDS = {
    "pro": STRIPE_PRO_PRICE_ID,
    "business": STRIPE_BUSINESS_PRICE_ID,
}


def create_stripe_customer(email: str) -> str:
    """Create a Stripe customer and return the customer ID."""
    customer = stripe.Customer.create(email=email)
    return customer.id


def create_checkout_session(customer_id: str, plan: str) -> str:
    """Create a Stripe Checkout session for a subscription and return the URL."""
    if plan not in PRICE_IDS:
        raise ValueError(f"Invalid plan: {plan}. Must be 'pro' or 'business'.")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
        mode="subscription",
        success_url="https://videomind.ai/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://videomind.ai/cancel",
    )

    return session.url
