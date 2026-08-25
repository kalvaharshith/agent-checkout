"""
Timeline Viewer — Milestone 6.

Renders the append-only audit trail as a human-readable timeline.
Reads the database live — every reload shows the current state of history.
"""
import json
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.audit import DB_PATH, init_db

app = FastAPI(title="Agent Checkout — Timeline Viewer", version="0.1.0")


def fetch_events():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT ts, actor, action, detail, reason FROM audit_events ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def classify(action: str) -> str:
    """Color the timeline edge: green = good, red = blocked/failed, gray = neutral."""
    if "rejected" in action or "failed" in action or "refused" in action:
        return "bad"
    if "approved" in action or "captured" in action or "paid" in action or "verified" in action:
        return "good"
    return "neutral"


PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Agent Checkout — Audit Timeline</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1115;
         color: #e6e6e6; margin: 0; padding: 40px 20px; }}
  h1   {{ font-size: 22px; color: #fff; }}
  .sub {{ color: #8a8f98; margin-bottom: 32px; font-size: 14px; }}
  .timeline {{ max-width: 880px; margin: 0 auto; }}
  .event {{ display: flex; gap: 16px; margin-bottom: 18px; }}
  .edge  {{ width: 6px; border-radius: 3px; flex-shrink: 0; }}
  .edge.good    {{ background: #2ecc71; box-shadow: 0 0 8px #2ecc7166; }}
  .edge.bad     {{ background: #e74c3c; box-shadow: 0 0 8px #e74c3c66; }}
  .edge.neutral {{ background: #4a5060; }}
  .card {{ background: #171a21; border: 1px solid #232833; border-radius: 10px;
          padding: 14px 18px; flex-grow: 1; }}
  .head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
          flex-wrap: wrap; }}
  .who  {{ font-weight: 600; color: #9fc3ff; font-size: 14px; }}
  .what {{ font-weight: 700; font-size: 15px; }}
  .what.good {{ color: #7ee2a8; }}
  .what.bad  {{ color: #ff8f7a; }}
  .when {{ color: #6b7280; font-size: 12px; font-family: 'Consolas', monospace; }}
  .why  {{ margin-top: 8px; font-size: 13.5px; color: #c9d1d9; }}
  .why::before {{ content: "why: "; color: #6b7280; font-style: italic; }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; color: #58a6ff; font-size: 12.5px; }}
  pre    {{ background: #0c0e12; border: 1px solid #232833; border-radius: 8px;
           padding: 10px; font-size: 11.5px; overflow-x: auto; color: #9aa4b2; }}
</style>
</head>
<body>
<div class="timeline">
  <h1>Agent Checkout — Audit Timeline</h1>
  <div class="sub">
    Append-only record of every action in the transaction lifecycle.
    Each step carries its reason. UPDATE and DELETE are refused by the database itself.
  </div>
  {events}
</div>
</body>
</html>"""


def render_event(row) -> str:
    kind = classify(row["action"])
    try:
        detail = json.loads(row["detail"])
        pretty = json.dumps(detail, indent=2, ensure_ascii=False)
    except Exception:
        pretty = row["detail"]

    # Pull a couple of headline fields out of the detail for a readable summary
    headline = ""
    try:
        d = json.loads(row["detail"])
        bits = []
        if "total_paise" in d:
            bits.append(f"total Rs.{d['total_paise'] / 100:,.2f}")
        if "budget_paise" in d:
            bits.append(f"budget Rs.{d['budget_paise'] / 100:,.2f}")
        if "amount_paise" in d:
            bits.append(f"amount Rs.{d['amount_paise'] / 100:,.2f}")
        if "payment_id" in d and d.get("payment_id"):
            bits.append(f"payment {d['payment_id']}")
        if "event" in d:
            bits.append(str(d["event"]))
        headline = " &middot; ".join(bits)
    except Exception:
        pass

    return f"""
  <div class="event">
    <div class="edge {kind}"></div>
    <div class="card">
      <div class="head">
        <span><span class="who">{row['actor']}</span> &nbsp; <span class="what {kind}">{row['action']}</span></span>
        <span class="when">{row['ts']}</span>
      </div>
      {f'<div style="margin-top:4px;color:#8a93a3;font-size:13px">{headline}</div>' if headline else ''}
      <div class="why">{row['reason'] or ''}</div>
      <details><summary>raw detail</summary><pre>{pretty}</pre></details>
    </div>
  </div>"""


@app.get("/timeline", response_class=HTMLResponse)
def timeline():
    rows = fetch_events()
    events_html = "\n".join(render_event(r) for r in rows) or "<i>trail is empty</i>"
    return PAGE.format(events=events_html)


@app.get("/")
def root():
    return {"viewer": "running", "timeline": "/timeline"}