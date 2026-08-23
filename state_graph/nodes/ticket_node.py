"""
state_graph/nodes/ticket_node.py

Unplanned mid-node failure path — DISTINCT from HITL.

HITL  = expected pause for a decision the agent is not allowed to make alone.
Ticket = unplanned: tool call errored, schema validation failed, model returned
         something the graph cannot act on.

A ticket is surfaced on the platform with status open | investigating | resolved
and the run resumes from its last checkpoint once resolved (not restarted).
"""

from __future__ import annotations

from typing import Any, Dict

from state_graph import persistence as store


class TicketNode:
    def open(
        self,
        run_id: str,
        node_id: str,
        error_type: str,
        error_message: str,
        state: Dict[str, Any],
    ) -> str:
        store.save_checkpoint(run_id, node_id, state)
        ticket_id = store.create_ticket(
            run_id, node_id, error_type, error_message, state
        )
        return ticket_id


class GraphFailure(Exception):
    """Raised after a ticket is opened so the runner stops cleanly."""

    def __init__(self, ticket_id: str, error_type: str, message: str):
        self.ticket_id = ticket_id
        self.error_type = error_type
        self.message = message
        super().__init__(f"Ticket {ticket_id}: [{error_type}] {message}")


def failure_gate(
    run_id: str,
    node_id: str,
    state: Dict[str, Any],
    error_type: str,
    error_message: str,
) -> None:
    """
    Call when an unplanned error is detected.
    Creates a real ticket from the detected failure (not a manual DB insert).
    """
    ticket_id = TicketNode().open(run_id, node_id, error_type, error_message, state)
    raise GraphFailure(ticket_id, error_type, error_message)
