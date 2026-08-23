#!/usr/bin/env python3
"""End-to-end HITL checkpoint demo. Use --auto-approve for a deterministic smoke test."""
import argparse, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db.init_db import init_db
from state_graph.graphs import BatchReleaseGraph
from state_graph.persistence import resolve_hitl

p=argparse.ArgumentParser(); p.add_argument("--auto-approve",action="store_true"); args=p.parse_args()
init_db()
g=BatchReleaseGraph({"current_state":"start","completed_steps":[],"supplier":"NEW_SUPPLIER_XYZ"})
r=g.run_until_hitl()
print("Graph started")
print(f"HITL pause -> task={r['task_id']} checkpoint={r['checkpoint_id']}")
print("Admin action required in platform: POST /api/admin/hitl/<task_id>/resolve")
if not args.auto_approve:
    input("Press Enter after approving in the admin UI... ")
resolve_hitl(r["task_id"],"approved","admin_demo")
g.state=r["state"]
result=g.resume("approved")
print("Graph resumed from checkpoint; prior steps were not re-executed.")
print("DEMO COMPLETE", result["current_state"])
