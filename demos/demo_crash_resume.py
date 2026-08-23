#!/usr/bin/env python3
"""Crash/restart demo. First run writes durable checkpoints; --resume continues the same run."""
import argparse, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db.init_db import init_db
from state_graph.graphs import SupplierCAPAGraph
from state_graph.persistence import load_latest_checkpoint

p=argparse.ArgumentParser(); p.add_argument("--resume",action="store_true"); args=p.parse_args()
init_db()
run_file=Path(".final_demo_run")
if not args.resume:
    g=SupplierCAPAGraph({"current_state":"start","completed_steps":[]})
    run_id,cp=g.run_until_checkpoint(); run_file.write_text(run_id)
    print(f"Checkpoint saved: {cp['checkpoint_id']} at state={cp['current_state']}")
    print("Simulating process crash now. Run this command to recover:")
    print("python demos/demo_crash_resume.py --resume")
    raise SystemExit(0)
run_id=run_file.read_text().strip()
g=SupplierCAPAGraph(run_id=run_id)
cp=load_latest_checkpoint(run_id)
if not cp: raise SystemExit("No checkpoint found")
g.state=cp["state"]
print(f"Loaded checkpoint {cp['checkpoint_id']} at state={cp['current_state']}")
result=g.resume()
print("Resumed without replaying completed states.")
print("DEMO COMPLETE", result["current_state"])
run_file.unlink(missing_ok=True)
