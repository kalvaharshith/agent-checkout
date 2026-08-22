"""Print the audit trail as a simple timeline. Run anytime."""
import sqlite3
import sys
from pathlib import Path

# The database lives at <project root>/db/audit.db
# This script lives at <project root>/scripts/show_audit.py
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "audit.db"

if not DB_PATH.exists():
    print("No audit database found at:")
    print(f"  {DB_PATH}")
    print()
    print("This means no catalog request has been logged yet.")
    print("Start the server, open http://localhost:8001/ in your browser,")
    print("refresh a few times, then run this script again.")
    sys.exit(0)

conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT ts, actor, action, detail, reason FROM audit_events ORDER BY id"
).fetchall()
conn.close()

if not rows:
    print("Database exists but the trail is empty.")
    print("Open http://localhost:8001/ in your browser, refresh a few times,")
    print("then run this script again.")
else:
    print(f"AUDIT TRAIL — {len(rows)} events")
    print("=" * 60)
    for ts, actor, action, detail, reason in rows:
        print(f"{ts} | {actor} | {action}")
        if reason:
            print(f"    why: {reason}")
        print(f"    detail: {detail}")
        print()