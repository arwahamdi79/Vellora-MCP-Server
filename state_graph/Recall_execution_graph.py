"""
state_graph/recall_execution_graph.py

PROBLEM 2 — Pet-insurance-style Claim? No — Product Recall Coordination
--------------------------------------------------------------------
(Adapted to Vellora pharma domain)

Why it cannot be a single pass:
  - Waits on external distributor acknowledgements / regulator response.
  - Can be rejected and need a reasoned appeal path.
  - Wrong resubmission wastes a real regulatory window.

Two LLM-call additions:
  1. Constrained ReAct — fill and submit only whitelisted recall forms/actions.
  2. Tree of Thoughts  — choose which appeal / scope argument to lead with.

HITL rule: recall_scope_above_threshold
Ticket path: malformed external response or tool error.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from state_graph import persistence as store
from state_graph.llm_client import tree_of_thoughts, constrained_react, rag_lookup
from state_graph.nodes.hitl_node import hitl_gate, HitlPause
from state_graph.nodes.ticket_node import failure_gate, GraphFailure

GRAPH_NAME = "recall_execution"

NODES = [
    "assess_scope",
    "hitl_large_scope",
    "choose_strategy",          # Tree of Thoughts
    "execute_recall_actions",   # Constrained ReAct
    "await_external",
    "finalize",
]


def initial_state(recall_id: str, units_affected: int = 1000, **kwargs) -> Dict[str, Any]:
    return {
        "recall_id": recall_id,
        "units_affected": units_affected,
        "strategy": None,
        "strategies": [],
        "actions_done": [],
        "external_ack": False,
        "status": "started",
        "completed_nodes": [],
        "_hitl_decisions": {},
        **kwargs,
    }


def _run_node(run_id: str, node_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    if node_id in state.get("completed_nodes", []):
        return state

    if node_id == "assess_scope":
        state["scope_note"] = rag_lookup(
            f"product recall procedure for {state['units_affected']} units, recall {state['recall_id']}"
        )
        state["status"] = "scope_assessed"

    elif node_id == "hitl_large_scope":
        state = hitl_gate(
            run_id, node_id, state,
            rule_names=["recall_scope_above_threshold"],
        )
        decision = state.get("hitl_decision", "approved")
        if decision == "rejected":
            state["status"] = "rejected_by_admin"
            state.setdefault("completed_nodes", []).append(node_id)
            store.save_checkpoint(run_id, node_id, state)
            return state
        state["status"] = "scope_approved"

    elif node_id == "choose_strategy":
        # --- Tree of Thoughts ---
        strategies = tree_of_thoughts(
            f"Select best recall communication strategy for recall {state['recall_id']} "
            f"affecting {state['units_affected']} units"
        )
        state["strategies"] = strategies
        best = max(strategies, key=lambda s: float(s.get("score", 0)))
        state["strategy"] = best
        state["status"] = "strategy_chosen"

    elif node_id == "execute_recall_actions":
        # --- Constrained ReAct (whitelist only) ---
        allowed = [
            "create_recall_record",
            "notify_distributors",
            "file_regulator_form",
            "quarantine_stock",
        ]
        if state.get("force_fail"):
            failure_gate(
                run_id, node_id, state,
                error_type="ExternalAPIError",
                error_message="Regulator portal returned malformed JSON — cannot parse acknowledgement",
            )
        for action in ["create_recall_record", "notify_distributors", "quarantine_stock"]:
            result = constrained_react(action, allowed, context=state["recall_id"])
            if not result["ok"]:
                failure_gate(
                    run_id, node_id, state,
                    error_type="ConstrainedActionDenied",
                    error_message=result.get("error", "denied"),
                )
            state.setdefault("actions_done", []).append(action)
        state["status"] = "actions_submitted"

    elif node_id == "await_external":
        # Simulated wait state — in production a webhook would resume
        if state.get("simulate_external_timeout"):
            failure_gate(
                run_id, node_id, state,
                error_type="ExternalTimeout",
                error_message="Distributor acknowledgement not received within expected window",
            )
        state["external_ack"] = True
        state["status"] = "external_acked"

    elif node_id == "finalize":
        state["status"] = "recall_closed"
        store.update_run_status(run_id, "completed")

    state.setdefault("completed_nodes", []).append(node_id)
    store.save_checkpoint(run_id, node_id, state)
    return state


def start(recall_id: str, units_affected: int = 1000, **kwargs) -> Dict[str, Any]:
    run_id = store.create_run(GRAPH_NAME)
    state = initial_state(recall_id, units_affected=units_affected, **kwargs)
    store.save_checkpoint(run_id, "start", state)
    return {"run_id": run_id, "state": state}


def resume(run_id: str, hitl_decision: Optional[str] = None) -> Dict[str, Any]:
    ckpt = store.load_checkpoint(run_id)
    if not ckpt:
        raise ValueError(f"No checkpoint for run {run_id}")
    state = ckpt["state"]
    if hitl_decision:
        state.setdefault("_hitl_decisions", {})[ckpt["node_id"]] = hitl_decision
        state["_hitl_decisions"]["hitl_large_scope"] = hitl_decision
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


def run(recall_id: str, units_affected: int = 1000, **kwargs) -> Dict[str, Any]:
    started = start(recall_id, units_affected=units_affected, **kwargs)
    return _advance(started["run_id"], started["state"])
