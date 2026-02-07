# app/routers/stripe_webhook.py
import stripe
from fastapi import APIRouter, Request, HTTPException
from app.config import STRIPE_WEBHOOK_SECRET, DATABASE_URL
from app.database import get_connection

router = APIRouter()


def _get_user_by_stripe_customer(db_path, customer_id):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _update_plan_by_customer_id(db_path, customer_id, plan):
    conn = get_connection(db_path)
    conn.execute("UPDATE users SET plan = ? WHERE stripe_customer_id = ?", (plan, customer_id))
    conn.commit()
    conn.close()


@router.post("/api/v1/stripe/webhook")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        customer_id = data_object.get("customer")
        plan = data_object.get("metadata", {}).get("plan", "pro")
        if customer_id:
            _update_plan_by_customer_id(DATABASE_URL, customer_id, plan)

    elif event_type == "customer.subscription.deleted":
        customer_id = data_object.get("customer")
        if customer_id:
            _update_plan_by_customer_id(DATABASE_URL, customer_id, "free")

    return {"status": "ok"}
