"""
planning/domain.py — Vellora deviation-response domain model.

This file is OURS, not the toolkit's. It describes *what* the Deviation Response
Agent plans over. The toolkit (planning_lab.algorithms.*) describes *how* it
searches. Keep that separation: no search logic belongs in this file.

Domain: Vellora Therapeutics pharmaceutical manufacturing.
Trigger: a batch fails QA and the deviation must be contained while supply
commitments are kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Sub-task taxonomy
# --------------------------------------------------------------------------- #

class SubtaskType(str, Enum):
    """
    The shape of a sub-task, which is what `planning/routing.py` routes on.

    Shape -- not topic -- decides the planner. Two sub-tasks about completely
    different tables route the same way if they have the same shape.
    """

    #: One correct answer, defined by SQL. No LLM planner.
    DETERMINISTIC_LOOKUP = "deterministic_lookup"

    #: Arithmetic / single-pass reasoning over retrieved rows. -> Plan-and-Solve
    SINGLE_PASS_REASONING = "single_pass_reasoning"

    #: Several defensible answers; value is in comparing candidates. -> ToT
    AMBIGUOUS_RANKING = "ambiguous_ranking"

    #: High branching, expensive to be wrong, AND a real validator exists. -> LATS
    HIGH_BRANCH_VALIDATED = "high_branch_validated"

    #: Prose output, cheap to regenerate, checkable against a rubric. -> Self-Refine
    CHEAP_REVISABLE_TEXT = "cheap_revisable_text"

    #: Writes to the MCP server. Gated on the grounded validator. No LLM.
    WRITE_GATE = "write_gate"


@dataclass(frozen=True)
class Subtask:
    """A node in the deviation-response DAG."""

    id: str
    title: str
    type: SubtaskType
    depends_on: tuple[str, ...] = ()
    #: Free-text instruction handed to whichever planner owns this node.
    instruction: str = ""

    def __post_init__(self) -> None:
        if self.id in self.depends_on:
            raise ValueError(f"Subtask {self.id!r} depends on itself")


# --------------------------------------------------------------------------- #
# The canonical DAG for the deviation-response request
# --------------------------------------------------------------------------- #
#
# Decomposition-first generates a plan shaped like this in one shot.
# Dynamic decomposition may produce a *different* graph -- extra nodes after an
# early observation, e.g. a second scope pass when the supplier-lot cohort turns
# out to span another line. That divergence is the evidence the lab asks for, so
# do NOT force the dynamic path to reproduce this graph.

CANONICAL_SUBTASKS: tuple[Subtask, ...] = (
    Subtask(
        id="T1",
        title="trace_impact",
        type=SubtaskType.DETERMINISTIC_LOOKUP,
        depends_on=(),
        instruction=(
            "Given the failed batch, return TWO cohorts: (a) batches produced on "
            "the same line inside the same cleaning-cycle window, (b) batches "
            "consuming the same raw-material supplier lot, on ANY line. "
            "Return batch ids with line, lot, status and current allocation."
        ),
    ),
    Subtask(
        id="T2",
        title="classify_scope",
        type=SubtaskType.AMBIGUOUS_RANKING,
        depends_on=("T1",),
        instruction=(
            "Assign every batch from T1 to exactly one tier: QUARANTINE, WATCH, "
            "or CLEAR. Justify each. Over-quarantine scraps saleable stock; "
            "under-quarantine ships contaminated product. Consider several "
            "tierings before committing."
        ),
    ),
    Subtask(
        id="T3",
        title="assess_supply_risk",
        type=SubtaskType.SINGLE_PASS_REASONING,
        depends_on=("T2",),
        instruction=(
            "For each medicine touched by the QUARANTINE tier, compute "
            "uncommitted stock after quarantine, open order quantity, and the "
            "earliest date the commitment breaks. Return a shortfall table."
        ),
    ),
    Subtask(
        id="T3b",
        title="check_line_status",
        type=SubtaskType.DETERMINISTIC_LOOKUP,
        depends_on=("T2",),
        instruction=(
            "Return every production line with its current hold status "
            "(cleaning / maintenance / free) and next free window."
        ),
    ),
    Subtask(
        id="T4",
        title="plan_recovery",
        type=SubtaskType.HIGH_BRANCH_VALIDATED,
        depends_on=("T3", "T3b"),
        instruction=(
            "Propose replacement production orders that close the shortfall from "
            "T3. For each: medicine, line, quantity, supplier, supplier lot, "
            "planned start, need-by, QA approver. Must not reuse the suspect lot "
            "and must not target a held line."
        ),
    ),
    Subtask(
        id="T5",
        title="draft_notices",
        type=SubtaskType.CHEAP_REVISABLE_TEXT,
        depends_on=("T4",),
        instruction=(
            "Draft (a) an internal QA hold notice and (b) a regulatory deviation "
            "summary. Rubric: state batch ids, root-cause hypothesis, scope and "
            "its justification, containment actions with owners, recovery plan, "
            "and the approver. No speculation stated as fact."
        ),
    ),
    Subtask(
        id="T6",
        title="commit",
        type=SubtaskType.WRITE_GATE,
        depends_on=("T5",),
        instruction=(
            "Write the quarantine status changes and the replacement production "
            "orders through the MCP server. Refuse if the grounded validator has "
            "not returned success."
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Request + plan payloads
# --------------------------------------------------------------------------- #

@dataclass
class DeviationRequest:
    """The real request a Vellora production planner sends today."""

    raw_text: str
    failed_batch_id: Optional[int] = None
    detected_line_id: Optional[int] = None
    #: Free-text finding, e.g. "microbial contamination, settle plate excursion".
    finding: str = ""
    #: Commitments the planner explicitly wants protected.
    protect_medicine_ids: List[int] = field(default_factory=list)

    def as_prompt(self) -> str:
        return self.raw_text


@dataclass
class RecoveryOrder:
    """One proposed replacement production order (output of T4)."""

    medicine_id: int
    line_id: int
    quantity: int
    supplier_id: int
    supplier_lot: Optional[str] = None
    planned_start: Optional[str] = None   # ISO date
    need_by: Optional[str] = None         # ISO date
    qa_approver_employee_id: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RecoveryOrder":
        def _int(v):
            return None if v in (None, "") else int(v)

        return cls(
            medicine_id=_int(d.get("medicine_id")),
            line_id=_int(d.get("line_id")),
            quantity=_int(d.get("quantity")) or 0,
            supplier_id=_int(d.get("supplier_id")),
            supplier_lot=d.get("supplier_lot"),
            planned_start=d.get("planned_start"),
            need_by=d.get("need_by"),
            qa_approver_employee_id=_int(d.get("qa_approver_employee_id")),
        )


@dataclass
class RecoveryPlan:
    """
    The full candidate T4 output. This is what `VelloraEnvironment.evaluate()`
    validates, and therefore what LATS and Reflexion are scored on.
    """

    quarantine_batch_ids: List[int] = field(default_factory=list)
    watch_batch_ids: List[int] = field(default_factory=list)
    orders: List[RecoveryOrder] = field(default_factory=list)
    rationale: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RecoveryPlan":
        return cls(
            quarantine_batch_ids=[int(b) for b in d.get("quarantine_batch_ids", [])],
            watch_batch_ids=[int(b) for b in d.get("watch_batch_ids", [])],
            orders=[RecoveryOrder.from_dict(o) for o in d.get("orders", [])],
            rationale=d.get("rationale", ""),
        )


#: Emitted into every T4 prompt so the environment can parse what comes back.
#: Keep this in the prompt -- an unparseable candidate scores 0 and wastes a
#: whole MCTS rollout.
PLAN_OUTPUT_CONTRACT = """
Return your answer as a single JSON object in a ```json fenced block:

```json
{
  "quarantine_batch_ids": [1042, 1043],
  "watch_batch_ids": [1051],
  "orders": [
    {
      "medicine_id": 12,
      "line_id": 7,
      "quantity": 5000,
      "supplier_id": 4,
      "supplier_lot": "SL-5120",
      "planned_start": "2026-08-20",
      "need_by": "2026-09-02",
      "qa_approver_employee_id": 204
    }
  ],
  "rationale": "one short paragraph"
}
```
""".strip()
