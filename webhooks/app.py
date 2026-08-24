"""
Webhook receiver — Milestone 5.

Razorpay calls THIS server when a payment completes. Before trusting anything,
we verify the X-Razorpay-Signature header: HMAC-SHA256 over the RAW body,
keyed with WEBHOOK_SECRET.

Rule: an unverified webhook is hostile noise (logged, rejected, 400).
A verified webhook is appended to the audit trail with the reason we trust it.
"""
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from audit.audit import write_event

app = FastAPI(title="Agent Checkout Webhook Receiver", version="0.1.0")

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


def verify_signature(raw_body: bytes, received_sig: str) -> bool:
    """HMAC-SHA256 of the raw body with our secret must equal the received signature."""
    if not WEBHOOK_SECRET:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)


@app.get("/health")
def health():
    return {"status": "ok", "secret_loaded": bool(WEBHOOK_SECRET)}


@app.post("/webhook")
async def receive_webhook(request: Request):
    raw = await request.body()   # RAW bytes — the signature covers exact bytes, not parsed JSON
    received_sig = request.headers.get("x-razorpay-signature", "")

    if not verify_signature(raw, received_sig):
        write_event(
            actor="webhook",
            action="webhook_rejected",
            detail={
                "signature_present": bool(received_sig),
                "body_preview": raw[:200].decode(errors="replace"),
            },
            reason="HMAC verification FAILED — untrusted callback: wrong secret or tampering",
        )
        raise HTTPException(status_code=400, detail="invalid signature")

    event = json.loads(raw)
    event_name = event.get("event", "unknown")
    payment = event.get("payload", {}).get("payment", {}).get("entity", {})

    write_event(
        actor="webhook",
        action=f"webhook_verified:{event_name}",
        detail={
            "event": event_name,
            "payment_id": payment.get("id"),
            "amount_paise": payment.get("amount"),
            "status": payment.get("status"),
            "method": payment.get("method"),
        },
        reason="HMAC signature verified against WEBHOOK_SECRET — trusted Razorpay callback",
    )
    print(f"WEBHOOK VERIFIED: {event_name} | payment_id={payment.get('id')} | "
          f"amount={payment.get('amount')} | status={payment.get('status')}")
    return {"status": "received"}