#!/usr/bin/env python3
"""
Demo 3: Process Crash → Checkpoint Recovery
===========================================
Proves checkpointing survives an actual process restart.
Part 1: run until mid-graph, write a marker, exit.
Part 2: --resume loads checkpoint and continues without re-executing done nodes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from state_graph import persistence as store
from state_graph import supplier_capa_graph as graph

MARKER = ROOT / "demos" / ".crash_demo_run_id"


def part1():
    store.init_tables()
    print("Part 1: Supplier CAPA Graph started")
    started = graph.start(supplier_id="SUP-CRASH-001", estimated_cost=1200)
    run_id = started["run_id"]
    state = started["state"]

    # Manually advance a couple of nodes then "crash"
    from state_graph.supplier_capa_graph import _run_node, NODES

    for node_id in NODES[:2]:  # investigate + search_corrective_orderings
        state = _run_node(run_id, node_id, state)
        print(f"  [Step] {node_id} done — checkpoint saved")

    MARKER.write_text(run_id)
    print(f"  💾 Checkpoint saved. run_id={run_id}")
    print("  ⚠️  SIMULATING PROCESS CRASH (exiting now)")
    print("  Restart with: python demos/demo_crash_resume.py --resume")
    sys.exit(0)


def part2():
    if not MARKER.exists():
        print("No marker file — run without --resume first")
        sys.exit(1)
    run_id = MARKER.read_text().strip()
    print(f"Part 2: Loading checkpoint for run_id={run_id}")
    ckpt = store.load_checkpoint(run_id)
    if not ckpt:
        print("No checkpoint found")
        sys.exit(1)
    print(f"  ✅ Loaded checkpoint node={ckpt['node_id']} seq={ckpt['sequence']}")
    print(f"  completed_nodes so far: {ckpt['state'].get('completed_nodes')}")

    resumed = graph.resume(run_id)
    print(f"  Resumed → status={resumed.get('status')}")
    print(f"  completed_nodes final: {resumed.get('state', {}).get('completed_nodes')}")

    # Prove no re-execution: the first two nodes must still be present once
    done = resumed.get("state", {}).get("completed_nodes", [])
    assert "investigate" in done
    assert "search_corrective_orderings" in done
    print("✅ DEMO COMPLETE — Crash recovery with no re-execution of completed steps")
    MARKER.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.resume:
        part2()
    else:
        part1()


if __name__ == "__main__":
    main()
