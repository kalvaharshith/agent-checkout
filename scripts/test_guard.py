"""
M3 demo: the guard approves an honest cart and BLOCKS an over-budget upsell.
This is the exact scenario you will show on camera.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guard.guard import evaluate_cart, rupees

catalog = json.loads((ROOT / "merchant" / "catalog.json").read_text(encoding="utf-8"))
BUDGET_PAISE = 150000

# Scenario A - the honest cart the model proposed in M2
cart_a = [
    {"sku": "TK-001", "qty": 1},   # Water Bottle   Rs.499
    {"sku": "TK-002", "qty": 1},   # Hiking Socks   Rs.399
    {"sku": "TK-005", "qty": 1},   # Snack Pack     Rs.299
]

# Scenario B - the agent gets greedy: an upsell adds the headlamp
cart_b = [
    {"sku": "TK-001", "qty": 1},
    {"sku": "TK-002", "qty": 1},
    {"sku": "TK-005", "qty": 1},
    {"sku": "TK-004", "qty": 1},   # LED Headlamp   Rs.899  <- the upsell
]


def run_scenario(title, cart, merchant_id):
    print("=" * 66)
    print(f"SCENARIO: {title}")
    print("=" * 66)
    d = evaluate_cart(cart, merchant_id, BUDGET_PAISE, catalog)
    for name, passed, detail in d.checks:
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name:<18} {detail}")
    print("-" * 66)
    if d.approved:
        print(f"  VERDICT: APPROVED — payment for {rupees(d.total_paise)} may proceed.")
    else:
        print("  VERDICT: REJECTED — the guard blocked this payment.")
        print("           No Razorpay call is made. The flow halts here.")
    print()


run_scenario("A — the honest cart (as proposed in M2)", cart_a, "trailkart")
run_scenario("B — the agent gets greedy: an upsell pushes the cart over budget", cart_b, "trailkart")

print("Both decisions are in the audit trail. Verify with:")
print("  .venv\\Scripts\\python.exe scripts\\show_audit.py")