"""
M4: end-to-end — proposal → guard → real Razorpay payment link (test mode).

Scenario A: honest cart  -> guard approves -> payment link issued
Scenario B: greedy cart  -> guard rejects  -> NO Razorpay call at all

The merchant server does NOT need to be running for this script.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guard.guard import evaluate_cart, rupees
from guard.checkout import attempt_payment

catalog = json.loads((ROOT / "merchant" / "catalog.json").read_text(encoding="utf-8"))
BUDGET_PAISE = 150000
MISSION = "Buy a birthday gift for a close friend who loves hiking (under Rs.1,500)"

cart_honest = [
    {"sku": "TK-001", "qty": 1},
    {"sku": "TK-002", "qty": 1},
    {"sku": "TK-005", "qty": 1},
]
cart_greedy = [
    {"sku": "TK-001", "qty": 1},
    {"sku": "TK-002", "qty": 1},
    {"sku": "TK-005", "qty": 1},
    {"sku": "TK-004", "qty": 1},   # the upsell that breaks the budget
]


def run_scenario(title, cart, attempt_pay: bool):
    print("=" * 66)
    print(f"SCENARIO: {title}")
    print("=" * 66)

    decision = evaluate_cart(cart, "trailkart", BUDGET_PAISE, catalog)
    for name, passed, detail in decision.checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:<18} {detail}")
    print("-" * 66)

    if not decision.approved:
        print("  VERDICT: REJECTED — the guard blocked this payment.")
        print("           No Razorpay call is made. The flow halts here.\n")
        return

    print(f"  VERDICT: APPROVED — {rupees(decision.total_paise)} may proceed.")
    if attempt_pay:
        link = attempt_payment(decision, MISSION)
        if link:
            print(f"\n  PAYMENT LINK (test mode): {link['short_url']}")
            print(f"  Amount: {rupees(decision.total_paise)}  |  Status: {link['status']}")
            print("\n  >>> Open that URL in your browser and pay with the TEST UPI ID:")
            print("  >>>   success@razorpay   (always succeeds)")
            print("  >>>   failure@razorpay   (always fails — that's your backup failure demo)")
    print()


print("SCENARIO A — honest cart: guard should approve, then a real payment link is issued")
run_scenario("A — honest cart", cart_honest, attempt_pay=True)

print("SCENARIO B — greedy upsell: guard must reject; checkout never touches Razorpay")
run_scenario("B — greedy upsell", cart_greedy, attempt_pay=False)

print("=" * 66)
print("Audit trail now contains the full story of both runs. View with:")
print("  .venv\\Scripts\\python.exe scripts\\show_audit.py")