"""
The Buyer Agent — Milestone 2 (Groq version).

Mission in, cart proposal out. This agent NEVER touches payment APIs.
It only *proposes*. Deterministic code verifies everything it says:
totals are recomputed from catalog prices, never taken from the model.

Every step lands in the audit trail.
"""
import json
import os
import sys
from pathlib import Path

import requests
from openai import OpenAI
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from audit.audit import write_event

# Groq configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment variables")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

MODEL = "openai/gpt-oss-120b"  # Update after running list_models.py
MERCHANT_URL = "http://127.0.0.1:8001"

MISSION = {
    "goal": "Buy a birthday gift for a close friend who loves hiking.",
    "budget_paise": 150000,  # Rs.1,500 — the hard budget
    "currency": "INR",
    "preferences": [
        "items must be hiking/outdoor related",
        "2-3 items that work together as one coherent gift",
        "stay strictly under budget",
    ],
}

SYSTEM_PROMPT = (
    "You are a careful personal-shopping agent acting for a user with a strict budget. "
    "You may ONLY propose items that exist in the catalog you are shown — never invent SKUs. "
    "Think about what makes a thoughtful, coherent gift, "
    "then call the propose_cart tool exactly once."
)

# OpenAI-style tool definition (Groq-compatible)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_cart",
            "description": (
                "Submit your final cart proposal. Include only SKUs from the catalog. "
                "Your reasoning should explain why these items fit the mission."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sku": {"type": "string"},
                                "qty": {"type": "integer", "minimum": 1},
                            },
                            "required": ["sku", "qty"],
                        },
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this cart fits the mission.",
                    },
                },
                "required": ["items", "reasoning"],
            },
        }
    }
]

def rupees(paise: int) -> str:
    return f"Rs.{paise / 100:,.2f}"

def run_buyer() -> None:
    print("BUYER AGENT — mission starting")
    print(f"  goal:   {MISSION['goal']}")
    print(f"  budget: {rupees(MISSION['budget_paise'])}")
    print(f"  model:  {MODEL} (Groq)")
    print()

    # 1 ── mission received (audit)
    write_event(
        actor="buyer_agent",
        action="mission_received",
        detail=MISSION,
        reason="operator started a buying mission",
    )

    # 2 ── discover the catalog over HTTP
    print("Fetching catalog from merchant ...")
    try:
        resp = requests.get(f"{MERCHANT_URL}/catalog", timeout=10)
        resp.raise_for_status()
        catalog = resp.json()
    except Exception as exc:
        print("COULD NOT REACH THE MERCHANT.")
        print("Is the merchant server running in your other terminal? If not, start it with:")
        print("  .venv\\Scripts\\python.exe -m uvicorn merchant.app:app --port 8001 --reload")
        print(f"\nUnderlying error: {exc}")
        return

    write_event(
        actor="buyer_agent",
        action="catalog_fetched",
        detail={"merchant": catalog["merchant"]["id"], "item_count": len(catalog["items"])},
        reason="discover what the merchant sells before proposing anything",
    )
    print(f"Got catalog: {catalog['merchant']['name']} — {len(catalog['items'])} items\n")

    # 3 ── ask Groq to propose a cart
    print("Asking Groq to reason about the mission ...\n")
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"MISSION:\n{json.dumps(MISSION, indent=2)}\n\n"
                    f"CATALOG (prices are in paise; 100 paise = Rs.1):\n"
                    f"{json.dumps(catalog['items'], indent=2)}\n\n"
                    "Propose your cart now using the propose_cart tool."
                ),
            }
        ],
        tools=TOOLS,
        tool_choice="required",
    )
    
    # Parse OpenAI-style response
    proposal = None
    if response.choices[0].message.tool_calls:
        tool_call = response.choices[0].message.tool_calls[0]
        if tool_call.function.name == "propose_cart":
            proposal = json.loads(tool_call.function.arguments)
    
    if proposal is None:
        print("Model did not return a cart proposal. Raw response:")
        print(response)
        return

    # 4 ── VERIFY: recompute everything from CATALOG prices.
    #      Never trust the model's math, prices, or SKUs.
    catalog_by_sku = {item["sku"]: item for item in catalog["items"]}
    cart_lines, unknown_skus = [], []
    for line in proposal["items"]:
        sku, qty = line["sku"], int(line.get("qty", 1))
        if sku in catalog_by_sku:
            item = catalog_by_sku[sku]
            cart_lines.append({
                "sku": sku,
                "name": item["name"],
                "qty": qty,
                "unit_price_paise": item["price_paise"],
                "line_total_paise": item["price_paise"] * qty,
            })
        else:
            unknown_skus.append(sku)

    total_paise = sum(line["line_total_paise"] for line in cart_lines)

    if unknown_skus:
        write_event(
            actor="buyer_agent",
            action="invalid_skus_dropped",
            detail={"skus": unknown_skus},
            reason="model proposed SKUs absent from the catalog; deterministic code dropped them",
        )

    write_event(
        actor="buyer_agent",
        action="cart_proposed",
        detail={
            "cart": cart_lines,
            "total_paise": total_paise,
            "budget_paise": MISSION["budget_paise"],
            "under_budget": total_paise <= MISSION["budget_paise"],
            "model_reasoning": proposal["reasoning"],
            "model": MODEL,
            "provider": "groq",
        },
        reason=f"model's stated reason: {proposal['reasoning'][:280]}",
    )

    # 5 ── human-readable summary
    print("CART PROPOSED")
    print("-" * 60)
    for line in cart_lines:
        print(f"  {line['qty']} x {line['name']:<32} {rupees(line['line_total_paise']):>12}")
    print("-" * 60)
    status = "UNDER BUDGET" if total_paise <= MISSION["budget_paise"] else "OVER BUDGET"
    print(f"  TOTAL: {rupees(total_paise)}  (budget {rupees(MISSION['budget_paise'])})  -> {status}")
    print()
    print(f"Model: {MODEL} (Groq)")
    print(f"Model's reasoning: {proposal['reasoning']}")
    print()
    print("No money moved. The guard (M3) and payment (M4) come next.")