"""
state_graph/nodes/hitl_node.py

Explicit HITL node type.
Conditions that must not let the agent decide alone:
  - amount / risk above a threshold
  - action that contradicts a stated policy
  - confidence score below a defendable bar

When a condition fires the graph pauses, persists full state, and opens a
task for an admin delivered through the platform UI. Resume only after the
admin acts through that UI.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from state_graph import persistence as store


# Default policy thresholds (defendable, domain-specific for Vellora)
HITL_RULES = {
    "batch_release_new_supplier": {
        "reason": "New supplier requires QA Manager sign-off before batch release (Batch Approval Policy §3.2).",
        "condition": lambda s: bool(s.get("is_new_supplier")),
    },
    "recall_scope_above_threshold": {
        "reason": "Recall affects more than 10,000 units — Operations Manager approval required (Product Recall Procedure).",
        "condition": lambda s: int(s.get("units_affected", 0)) > 10_000,
    },
    "capa_cost_above_threshold": {
        "reason": "Corrective action estimated cost exceeds $5,000 — manager approval required.",
        "condition": lambda s: float(s.get("estimated_cost", 0)) > 5000,
    },
    "low_confidence": {
        "reason": "Model confidence below 0.65 — human review required before irreversible action.",
        "condition": lambda s: float(s.get("confidence", 1.0)) < 0.65,
    },
    "sedation_or_admission": {
        "reason": "Irreversible clinical action (sedation/admission) may not be taken by the agent alone.",
        "condition": lambda s: s.get("action_type") in ("sedate", "admit"),
    },
}


class HITLNode:
    """
    Node that evaluates HITL conditions and, when one fires, creates a
    pending task and raises HitlPause so the graph runner stops.
    """

    def __init__(self, rule_names: list[str]):
        self.rule_names = rule_names

    def evaluate(self, state: Dict[str, Any]) -> Optional[str]:
        """Return the reason string if any rule fires, else None."""
        for name in self.rule_names:
            rule = HITL_RULES.get(name)
            if rule and rule["condition"](state):
                return rule["reason"]
        return None

    def pause(self, run_id: str, node_id: str, state: Dict[str, Any], reason: str) -> str:
        """Persist checkpoint + open HITL task. Returns task_id."""
        store.save_checkpoint(run_id, node_id, state)
        task_id = store.create_hitl_task(run_id, node_id, reason, state)
        return task_id


class HitlPause(Exception):
    """Raised to stop graph execution until an admin resolves the task."""

    def __init__(self, task_id: str, reason: str):
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"HITL pause: {reason} (task={task_id})")


def hitl_gate(
    run_id: str,
    node_id: str,
    state: Dict[str, Any],
    rule_names: list[str],
) -> Dict[str, Any]:
    """
    Call at the start of a sensitive node.
    If a rule fires: checkpoint, create task, raise HitlPause.
    If the state already carries an admin decision for this node, apply it and continue.
    """
    # Already decided by admin on a previous resume?
    decisions = state.get("_hitl_decisions", {})
    if node_id in decisions:
        state["hitl_decision"] = decisions[node_id]
        return state

    node = HITLNode(rule_names)
    reason = node.evaluate(state)
    if reason:
        task_id = node.pause(run_id, node_id, state, reason)
        raise HitlPause(task_id, reason)
    return state
