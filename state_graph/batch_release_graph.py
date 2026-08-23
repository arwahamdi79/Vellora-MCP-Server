"""
state_graph/batch_release_graph.py

PROBLEM 1 — Multi-step Batch Release Coordination
-------------------------------------------------
Why it cannot be a single pass:
  - Spans QA review, supplier qualification check, and release certificate.
  - Real branch: new supplier requires QA Manager HITL sign-off.
  - Failure mode: external LIMS timeout or schema validation error opens a ticket.

Two LLM-call additions inside nodes:
  1. Task decomposition  — build the ordered release sequence.
  2. RAG                — pull clinic/company chronic-care / batch-approval protocols.

HITL rule: batch_release_new_supplier
Ticket path: LIMS / tool call errors mid-node.
Checkpoint after every node transition.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from state_graph import persistence as store
from state_graph.llm_client import decompose_task, rag_lookup, constrained_react
from state_graph.nodes.hitl_node import hitl_gate, HitlPause
from state_graph.nodes.ticket_node import failure_gate, GraphFailure

GRAPH_NAME = "batch_release"

# Ordered nodes
NODES = [
    "decompose_release_plan",
    "fetch_protocols",
    "check_supplier",
    "hitl_new_supplier",          # HITL gate
    "run_release_actions",
    "finalize",
]


def initial_state(batch_id: str, is_new_supplier: bool = False, **kwargs) -> Dict[str, Any]:
    return {
        "batch_id": batch_id,
        "is_new_supplier": is_new_supplier,
        "steps": [],
        "protocols": "",
        "supplier_ok": False,
        "actions_done": [],
        "confidence": kwargs.get("confidence", 0.9),
        "status": "started",
        "completed_nodes": [],
        "_hitl_decisions": {},
        **kwargs,
    }


def _run_node(run_id: str, node_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one node; checkpoint on success."""
    if node_id in state.get("completed_nodes", []):
        return state  # no re-execution on resume

    if node_id == "decompose_release_plan":
        # --- Task decomposition ---
        goal = f"Release batch {state['batch_id']} under Vellora Batch Approval Policy"
        state["steps"] = decompose_task(goal)
        state["status"] = "plan_ready"

    elif node_id == "fetch_protocols":
        # --- RAG ---
        state["protocols"] = rag_lookup(
            f"batch approval policy and release criteria for batch {state['batch_id']}"
        )
        state["status"] = "protocols_loaded"

    elif node_id == "check_supplier":
        # Simulated supplier qualification check
        state["supplier_ok"] = not state.get("is_new_supplier", False)
        state["status"] = "supplier_checked"

    elif node_id == "hitl_new_supplier":
        # --- HITL gate ---
        state = hitl_gate(
            run_id, node_id, state,
            rule_names=["batch_release_new_supplier", "low_confidence"],
        )
        decision = state.get("hitl_decision", "approved")
        if decision == "rejected":
            state["status"] = "rejected_by_admin"
            state["completed_nodes"] = state.get("completed_nodes", []) + [node_id]
            store.save_checkpoint(run_id, node_id, state)
            return state
        state["supplier_ok"] = True
        state["status"] = "supplier_approved"

    elif node_id == "run_release_actions":
        # Constrained actions only
        allowed = ["update_batch_status", "write_certificate", "notify_qa"]
        # Simulate a tool failure when force_fail is set (for ticket demo)
        if state.get("force_fail"):
            failure_gate(
                run_id, node_id, state,
                error_type="ToolTimeout",
                error_message="LIMS update_batch_status timed out after 30s",
            )
        for action in ["update_batch_status", "write_certificate"]:
            result = constrained_react(action, allowed, context=state["batch_id"])
            if not result["ok"]:
                failure_gate(
                    run_id, node_id, state,
                    error_type="SchemaValidation",
                    error_message=result.get("error", "unknown"),
                )
            state.setdefault("actions_done", []).append(action)
        state["status"] = "actions_done"

    elif node_id == "finalize":
        state["status"] = "released"
        store.update_run_status(run_id, "completed")

    state.setdefault("completed_nodes", []).append(node_id)
    store.save_checkpoint(run_id, node_id, state)
    return state


def start(batch_id: str, is_new_supplier: bool = False, **kwargs) -> Dict[str, Any]:
    run_id = store.create_run(GRAPH_NAME)
    state = initial_state(batch_id, is_new_supplier=is_new_supplier, **kwargs)
    store.save_checkpoint(run_id, "start", state)
    return {"run_id": run_id, "state": state}


def resume(run_id: str, hitl_decision: Optional[str] = None) -> Dict[str, Any]:
    """Resume from latest checkpoint; optionally inject an admin HITL decision."""
    ckpt = store.load_checkpoint(run_id)
    if not ckpt:
        raise ValueError(f"No checkpoint for run {run_id}")
    state = ckpt["state"]
    if hitl_decision:
        node = ckpt["node_id"]
        state.setdefault("_hitl_decisions", {})[node] = hitl_decision
        # Also allow matching by logical HITL node name
        state["_hitl_decisions"]["hitl_new_supplier"] = hitl_decision
    return _advance(run_id, state)


def _advance(run_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    for node_id in NODES:
        if node_id in state.get("completed_nodes", []):
            continue
        try:
            state = _run_node(run_id, node_id, state)
            if state.get("status") == "rejected_by_admin":
                store.update_run_status(run_id, "rejected")
                return {"run_id": run_id, "state": state, "status": "rejected"}
        except HitlPause as e:
            return {
                "run_id": run_id,
                "state": state,
                "status": "awaiting_hitl",
                "task_id": e.task_id,
                "reason": e.reason,
            }
        except GraphFailure as e:
            return {
                "run_id": run_id,
                "state": state,
                "status": "failed",
                "ticket_id": e.ticket_id,
                "error": str(e),
            }
    store.update_run_status(run_id, "completed")
    return {"run_id": run_id, "state": state, "status": "completed"}


def run(batch_id: str, is_new_supplier: bool = False, **kwargs) -> Dict[str, Any]:
    started = start(batch_id, is_new_supplier=is_new_supplier, **kwargs)
    return _advance(started["run_id"], started["state"])
