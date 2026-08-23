#!/usr/bin/env python3
"""
Demo 2: Unplanned Failure → Ticket → Resolution → Resume
========================================================
Distinct from HITL: a real tool/timeout error opens a failure ticket.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from state_graph import persistence as store
from state_graph import recall_execution_graph as graph


def main():
    store.init_tables()
    print("Step 1: Recall Coordination Graph started (force_fail=True)")
    result = graph.run(
        recall_id="RCL-TICKET-001",
        units_affected=500,  # below HITL threshold so we hit the tool failure
        force_fail=True,
    )
    print(f"  status = {result.get('status')}")
    print(f"  run_id = {result.get('run_id')}")

    if result.get("status") != "failed":
        print("⚠️  Expected failed status with ticket")
        print(result)
        return

    ticket_id = result["ticket_id"]
    run_id = result["run_id"]
    print(f"Step 2: Tool error detected, ticket created")
    print(f"  ticket_id = {ticket_id}")
    print(f"  error = {result.get('error')}")

    ckpt = store.load_checkpoint(run_id)
    print(f"Step 3: State checkpointed at node={ckpt['node_id']}")

    tickets = store.list_tickets("open")
    print(f"Step 4: Platform sees {len(tickets)} open ticket(s)")

    print("Step 5: Admin resolves ticket (retry)")
    store.resolve_ticket(ticket_id, resolution="retry", resolved_by="demo_admin")
    # Clear force_fail in checkpoint state so retry succeeds
    state = ckpt["state"]
    state["force_fail"] = False
    # Remove the failed node from completed so it re-runs cleanly,
    # OR keep completed and skip — we re-run only the failed node by
    # ensuring it is NOT in completed_nodes.
    if ckpt["node_id"] in state.get("completed_nodes", []):
        state["completed_nodes"].remove(ckpt["node_id"])
    store.save_checkpoint(run_id, ckpt["node_id"], state)

    resumed = graph.resume(run_id)
    print(f"Step 6: Resumed → status={resumed.get('status')}")
    print(f"  completed_nodes = {resumed.get('state', {}).get('completed_nodes')}")
    print("✅ DEMO COMPLETE — Failure ticket and recovery OK")


if __name__ == "__main__":
    main()
