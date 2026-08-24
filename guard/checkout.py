"""
Checkout — Milestone 4.

THE ONLY FILE IN THE PROJECT ALLOWED TO IMPORT RAZORPAY.
The agent never sees payment APIs. The guard approves; this file executes
the approved decision. Structural separation = "gated" by architecture.
"""
import os
import sys
from pathlib import Path

import razorpay
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from audit.audit import write_event


def rupees(paise: int) -> str:
    return f"Rs.{paise / 100:,.2f}"


def _client() -> razorpay.Client:
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise RuntimeError("Razorpay keys missing — check .env (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET)")
    return razorpay.Client(auth=(key_id, key_secret))


def attempt_payment(guard_decision, mission_goal: str) -> dict | None:
    """
    Execute an APPROVED guard decision as a real Razorpay payment link (test mode).

    Returns a dict with the link info, or None if the decision wasn't approved
    (belt-and-suspenders: checkout refuses to even run without approval).
    """
    if not guard_decision.approved:
        write_event(
            actor="checkout",
            action="payment_attempt_refused",
            detail={"reason": "guard decision was not approved"},
            reason="checkout refuses to execute non-approved decisions — structural gate",
        )
        return None

    client = _client()
    description = "; ".join(
        f"{l['qty']}x {l['sku']} @ {rupees(l['unit_price_paise'])}"
        for l in guard_decision.verified_lines
    ) if hasattr(guard_decision, "verified_lines") else mission_goal

    write_event(
        actor="checkout",
        action="order_creation_started",
        detail={
            "amount_paise": guard_decision.total_paise,
            "merchant_id": guard_decision.merchant_id,
        },
        reason="guard approved this cart; creating a Razorpay order for exactly this amount",
    )

    try:
        # Payment Link API — the simplest way to a real, payable link
        link = client.payment_link.create({
            "amount": guard_decision.total_paise,      # paise, from the guard's own math
            "currency": "INR",
            "accept_partial": False,
            "description": description[:250],
            "reference_id": f"agentcart-{guard_decision.total_paise}-{os.urandom(3).hex()}",
            "notes": {
                "mission": mission_goal,
                "merchant_id": guard_decision.merchant_id,
                "source": "agent-checkout M4",
            },
        })
    except Exception as exc:
        write_event(
            actor="checkout",
            action="order_creation_failed",
            detail={"error": str(exc)},
            reason="Razorpay rejected the payment-link creation call",
        )
        print(f"RAZORPAY ERROR creating payment link: {exc}")
        return None

    write_event(
        actor="checkout",
        action="payment_link_created",
        detail={
            "link_id": link["id"],
            "amount_paise": guard_decision.total_paise,
            "short_url": link["short_url"],
            "status": link["status"],
        },
        reason="real test-mode payment link issued; human gate: a person must now open it and pay",
    )
    return link