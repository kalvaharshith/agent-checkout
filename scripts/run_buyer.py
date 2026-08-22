"""Run one buyer-agent mission: discover catalog, propose a cart. No money moves."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.buyer import run_buyer

if __name__ == "__main__":
    run_buyer()