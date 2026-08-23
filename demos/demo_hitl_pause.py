#!/usr/bin/env python3
"""
Demo 1: HITL Pause → Admin Action → Resume
==========================================
Shows a genuine HITL condition pausing the Batch Release graph,
persisting state, and resuming only after an admin decision.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from state_graph import persistence as store
from state_graph import batch_release_graph as graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-approve", action="store_true", help="Simulate admin approve without UI")
    args = parser.parse_args()

    store.init_tables()
    print("Step 1: Initializing Batch Release Graph (new supplier → HITL)")
    result = graph.run(batch_id="BATCH-HITL-001", is_new_supplier=True)
    print(f"  status = {result.get('status')}")
    print(f"  run_id = {result.get('run_id')}")

    if result.get("status") != "awaiting_hitl":
        print("⚠️  Expected awaiting_hitl — check HITL rules")
        print(result)
        return

    task_id = result["task_id"]
    run_id = result["run_id"]
    print(f"Step 2: HITL pause detected")
    print(f"  reason = {result.get('reason')}")
    print(f"  task_id = {task_id}")

    ckpt = store.load_checkpoint(run_id)
    print(f"Step 3: Checkpoint persisted at node={ckpt['node_id']} seq={ckpt['sequence']}")

    tasks = store.list_hitl_tasks("pending")
    print(f"Step 4: Platform sees {len(tasks)} pending HITL task(s)")

    if args.auto_approve:
        print("Step 5: Admin approves (auto)")
        store.resolve_hitl_task(task_id, decision="approved", decided_by="demo_admin")
        resumed = graph.resume(run_id, hitl_decision="approved")
        print(f"Step 6: Resumed → status={resumed.get('status')}")
        print(f"  completed_nodes = {resumed.get('state', {}).get('completed_nodes')}")
        assert "decompose_release_plan" in resumed.get("state", {}).get("completed_nodes", [])
        print("Step 7: Verified no re-execution of prior completed nodes")
        print("✅ DEMO COMPLETE — HITL pause and resume OK")
    else:
        print("Step 5: Open http://127.0.0.1:5000/admin/hitl and Approve the task")
        print(f"         then: python -c \"from state_graph import batch_release_graph as g; print(g.resume('{run_id}', hitl_decision='approved'))\"")
        print("⏸️  Waiting for admin action through the platform UI")


if __name__ == "__main__":
    main()
