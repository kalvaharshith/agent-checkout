"""
The Guard — Milestone 3.

A deterministic checkpoint between the agent and the payment API.

Design rules:
- No LLM calls. No network. Nothing external.
- Prices are ALWAYS recomputed from the catalog — never taken from the caller.
- Every decision (approve or reject) is written to the audit trail with a reason.
- Pure function: same inputs, same verdict, every single time.
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.audit import write_event

MERCHANT_ALLOWLIST = {"trailkart"}   # bounded: only these merchants may ever be paid
MAX_QTY_PER_ITEM = 5                 # bounded: no single-item hoarding
MAX_CART_LINES = 10                  # bounded: cart size sanity


def rupees(paise: int) -> str:
    return f"Rs.{paise / 100:,.2f}"


@dataclass
class GuardDecision:
    approved: bool
    merchant_id: str
    total_paise: int
    budget_paise: int
    verified_lines: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    violations: list = field(default_factory=list)

    def summary(self) -> str:
        if self.approved:
            return (f"APPROVED — total {rupees(self.total_paise)} "
                    f"within budget {rupees(self.budget_paise)}")
        return "REJECTED — " + "; ".join(self.violations)


def evaluate_cart(cart_lines, merchant_id, budget_paise, catalog) -> GuardDecision:
    """
    cart_lines:   list of {"sku": str, "qty": int} — NOTHING ELSE IS TRUSTED.
    merchant_id:  the merchant this cart belongs to
    budget_paise: the hard cap from the mission
    catalog:      the catalog dict (source of truth for prices)

    APPROVED means a payment for this exact cart, at prices recomputed here,
    MAY be attempted. It is not a payment; it is permission.
    """
    checks, violations = [], []

    def check(name, passed, detail):
        checks.append((name, passed, detail))
        if not passed:
            violations.append(f"{name}: {detail}")

    # 1 - cart not empty
    check("cart_not_empty", len(cart_lines) > 0,
          "cart contained no items" if not cart_lines else f"{len(cart_lines)} line items")

    # 2 - merchant allow-list (bounded)
    merchant_ok = merchant_id in MERCHANT_ALLOWLIST
    check("merchant_allowed", merchant_ok,
          (f"merchant '{merchant_id}' not on allow-list {sorted(MERCHANT_ALLOWLIST)}"
           if not merchant_ok else f"merchant '{merchant_id}' allow-listed"))

    # 3 - SKUs valid; prices RECOMPUTED from catalog, never trusted from caller
    catalog_by_sku = {i["sku"]: i for i in catalog["items"]}
    verified_lines, bad_skus = [], []
    for line in cart_lines:
        sku = line.get("sku")
        qty = int(line.get("qty", 0))
        if sku not in catalog_by_sku:
            bad_skus.append(str(sku))
            continue
        item = catalog_by_sku[sku]
        if not item.get("in_stock", False):
            bad_skus.append(f"{sku} (out of stock)")
            continue
        verified_lines.append({
            "sku": sku,
            "qty": qty,
            "unit_price_paise": item["price_paise"],   # from catalog, NOT from caller
            "line_total_paise": item["price_paise"] * qty,
        })
    check("skus_valid", not bad_skus,
          f"unknown/unavailable SKUs: {bad_skus}" if bad_skus else "all SKUs verified against catalog")

    # 4 - quantity and cart-size sanity (bounded)
    qty_ok = (all(1 <= l["qty"] <= MAX_QTY_PER_ITEM for l in verified_lines)
              and len(verified_lines) <= MAX_CART_LINES)
    check("qty_sane", qty_ok,
          f"qty must be 1..{MAX_QTY_PER_ITEM} per item, at most {MAX_CART_LINES} lines")

    # 5 - THE HARD CAP: recomputed total vs budget
    total_paise = sum(l["line_total_paise"] for l in verified_lines)
    budget_ok = total_paise <= budget_paise
    check("within_budget", budget_ok,
          (f"total {rupees(total_paise)} exceeds budget {rupees(budget_paise)} "
           f"by {rupees(total_paise - budget_paise)}"
           if not budget_ok else f"total {rupees(total_paise)} within budget {rupees(budget_paise)}"))

    approved = not violations

    decision = GuardDecision(
        approved=approved,
        merchant_id=merchant_id,
        total_paise=total_paise,
        budget_paise=budget_paise,
        verified_lines=verified_lines,
        checks=checks,
        violations=violations,
    )

    # every evaluation lands in the trail — approvals AND rejections
    write_event(
        actor="guard",
        action="guard_approved" if approved else "guard_rejected",
        detail={
            "merchant_id": merchant_id,
            "verified_cart": verified_lines,
            "total_paise": total_paise,
            "budget_paise": budget_paise,
            "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in checks],
        },
        reason=decision.summary(),
    )
    return decision