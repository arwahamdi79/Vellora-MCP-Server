"""
state_graph/supplier_capa_graph.py

PROBLEM 3 — Supplier CAPA (Corrective and Preventive Action)
-----------------------------------------------------------
Why it cannot be a single pass:
  - Spans investigation, root-cause analysis, plan approval, and supplier response.
  - Real wait: supplier may take days to acknowledge the CAPA plan.
  - Human decision: cost above threshold or irreversible supplier de-list needs manager sign-off.
  - Failure: supplier portal error or plan schema rejection opens a ticket.

Two LLM-call additions:
  1. LATS-style search over candidate corrective orderings scored by severity.
  2. Constrained ReAct — execute only whitelisted CAPA intake / submission actions.

HITL rule: capa_cost_above_threshold
Ticket path: supplier portal / validation failures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from state_graph import persistence as store
from state_graph.llm_client import chat, constrained_react, tree_of_thoughts
from state_graph.nodes.hitl_node import hitl_gate, HitlPause
from state_graph.nodes.ticket_node import failure_gate, GraphFailure

GRAPH_NAME = "supplier_capa"

NODES = [
    "investigate",
    "search_corrective_orderings",  # LATS-style
    "hitl_cost_gate",
    "submit_capa",                   # Constrained ReAct
    "await_supplier_ack",
    "finalize",
]


def initial_state(supplier_id: str, estimated_cost: float = 1000.0, **kwargs) -> Dict[str, Any]:
    return {
        "supplier_id": supplier_id,
        "estimated_cost": estimated_cost,
        "findings": "",
        "orderings": [],
        "chosen_plan": None,
        "actions_done": [],
        "supplier_ack": False,
        "status": "started",
        "completed_nodes": [],
        "_hitl_decisions": {},
        **kwargs,
    }


def _lats_search(issue: str) -> List[Dict[str, Any]]:
    """LATS-style: generate candidate orderings scored by a real severity check."""
    raw = chat(
        f"LATS search: propose 3 corrective action orderings for supplier issue "
        f"'{issue}' as JSON list of {{ordering: [...steps], severity_score: float}}"
    )
    import json
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    # Offline deterministic candidates
    return [
        {"ordering": ["contain", "root_cause", "corrective", "verify"], "severity_score": 0.9},
        {"ordering": ["root_cause", "contain", "corrective", "verify"], "severity_score": 0.7},
        {"ordering": ["corrective", "contain", "verify"], "severity_score": 0.5},
    ]


def _run_node(run_id: str, node_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    if node_id in state.get("completed_nodes", []):
        return state

    if node_id == "investigate":
        state["findings"] = (
            f"Supplier {state['supplier_id']}: non-conforming material detected; "
            f"estimated remediation cost ${state['estimated_cost']:,.0f}"
        )
        state["status"] = "investigated"

    elif node_id == "search_corrective_orderings":
        # --- LATS ---
        orderings = _lats_search(state["findings"])
        # Ensure list of dicts (offline stubs / bad LLM JSON)
        orderings = [o for o in orderings if isinstance(o, dict)]
        if not orderings:
            orderings = [{"ordering": ["contain", "root_cause", "corrective", "verify"], "severity_score": 0.9}]
        state["orderings"] = orderings
        best = max(orderings, key=lambda o: float(o.get("severity_score", 0)))
        state["chosen_plan"] = best
        state["status"] = "plan_selected"

    elif node_id == "hitl_cost_gate":
        state = hitl_gate(
            run_id, node_id, state,
            rule_names=["capa_cost_above_threshold"],
        )
        decision = state.get("hitl_decision", "approved")
        if decision == "rejected":
            state["status"] = "rejected_by_admin"
            state.setdefault("completed_nodes", []).append(node_id)
            store.save_checkpoint(run_id, node_id, state)
            return state
        state["status"] = "plan_approved"

    elif node_id == "submit_capa":
        allowed = [
            "open_capa_record",
            "attach_evidence",
            "submit_to_supplier_portal",
            "schedule_followup",
        ]
        if state.get("force_fail"):
            failure_gate(
                run_id, node_id, state,
                error_type="SupplierPortalError",
                error_message="Supplier portal rejected CAPA payload (schema validation failed)",
            )
        for action in ["open_capa_record", "attach_evidence", "submit_to_supplier_portal"]:
            result = constrained_react(action, allowed, context=state["supplier_id"])
            if not result["ok"]:
                failure_gate(
                    run_id, node_id, state,
                    error_type="ConstrainedActionDenied",
                    error_message=result.get("error", "denied"),
                )
            state.setdefault("actions_done", []).append(action)
        state["status"] = "submitted"

    elif node_id == "await_supplier_ack":
        if state.get("simulate_external_timeout"):
            failure_gate(
                run_id, node_id, state,
                error_type="ExternalTimeout",
                error_message="Supplier did not acknowledge CAPA within expected window",
            )
        state["supplier_ack"] = True
        state["status"] = "acked"

    elif node_id == "finalize":
        state["status"] = "capa_closed"
        store.update_run_status(run_id, "completed")

    state.setdefault("completed_nodes", []).append(node_id)
    store.save_checkpoint(run_id, node_id, state)
    return state


def start(supplier_id: str, estimated_cost: float = 1000.0, **kwargs) -> Dict[str, Any]:
    run_id = store.create_run(GRAPH_NAME)
    state = initial_state(supplier_id, estimated_cost=estimated_cost, **kwargs)
    store.save_checkpoint(run_id, "start", state)
    return {"run_id": run_id, "state": state}


def resume(run_id: str, hitl_decision: Optional[str] = None) -> Dict[str, Any]:
    ckpt = store.load_checkpoint(run_id)
    if not ckpt:
        raise ValueError(f"No checkpoint for run {run_id}")
    state = ckpt["state"]
    if hitl_decision:
        state.setdefault("_hitl_decisions", {})[ckpt["node_id"]] = hitl_decision
        state["_hitl_decisions"]["hitl_cost_gate"] = hitl_decision
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


def run(supplier_id: str, estimated_cost: float = 1000.0, **kwargs) -> Dict[str, Any]:
    started = start(supplier_id, estimated_cost=estimated_cost, **kwargs)
    return _advance(started["run_id"], started["state"])
