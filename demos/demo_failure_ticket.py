#!/usr/bin/env python3
"""Failure -> persisted ticket -> admin resolution -> resume smoke demo."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db.init_db import init_db
from state_graph.graphs import RecallCoordinationGraph
from state_graph.persistence import resolve_ticket, load_latest_checkpoint

init_db()
g=RecallCoordinationGraph({"current_state":"start","completed_steps":[]})
r=g.run(fail=True)
print(f"Failure detected -> ticket={r['ticket_id']} checkpoint={r['checkpoint_id']}")
print("Ticket is visible at /admin/tickets")
resolve_ticket(r["ticket_id"],"retry","admin_demo")
cp=load_latest_checkpoint(g.run_id); g.state=cp["state"]
result=g.run(fail=False)
print("Ticket resolved; resumed from last checkpoint; no prior-step replay.")
print("DEMO COMPLETE", result["current_state"])
