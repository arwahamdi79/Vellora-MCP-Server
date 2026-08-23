#!/usr/bin/env python3
"""Create checkpoint / HITL / ticket tables in the shared DB."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from state_graph.persistence import init_tables, DB_PATH

if __name__ == "__main__":
    init_tables()
    print(f"✅ State graph tables ready at {DB_PATH}")
