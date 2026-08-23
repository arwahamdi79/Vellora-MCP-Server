"""
planning/domain.py — Vellora QA-failure containment domain model.

This file is OURS, not the toolkit's. It describes *what* the Deviation Response
Agent plans over. The toolkit (planning_lab.algorithms.*) describes *how* it
searches. No search logic belongs here.

Written against the REAL schema in db/schema.sql:
    Employee(EmployeeID, FullName, Email, Department, Role, AccountStatus)
    Medicine(MedicineID, MedicineName, ..., ManufacturingStatus)
    Supplier(SupplierID, CompanyName, ..., MaterialSupplied)
    Production_Order(ProductionOrderID, MedicineID, SupplierID, PlannedQuantity,
                     CreationDate, ProductionStatus, ResponsibleEmployeeID)
    Manufacturing_Batch(BatchID, ProductionOrderID, MedicineID,
                        ManufacturingDate, ExpiryDate, BatchStatus,
                        CurrentLocation)
    Quality_Test(TestID, BatchID, TestType, TestResult, TestDate,
                 QAEmployeeID, Remarks)
    Product_Recall(RecallID, BatchID UNIQUE, RecallDate, RecallReason,
                   RecallStatus, AuthorizedManagerID)

THE REQUEST
-----------
    "Batch 1042 failed its sterility test. Contain it."

Why it is a planning problem and not a lookup:

  * The blast radius is a search, not a field. Sibling batches share a
    ProductionOrderID; other batches share the SupplierID that supplied the
    implicated material; others merely share CurrentLocation. Which cohorts
    count is a judgement call that changes the whole downstream plan.

  * The cost is asymmetric and status-dependent. A batch already 'Distributed'
    needs a Product_Recall -- customer-facing, expensive, irreversible. An
    'Approved' batch only needs its BatchStatus flipped to 'Rejected'. Treating
    the two alike is wrong in both directions.

  * Constraints genuinely conflict. Product_Recall.BatchID is UNIQUE, so a batch
    already recalled cannot be recalled again. Only a 'QA Manager' may authorize
    a recall -- 'QA Staff' may not. Replacement orders must not re-source from
    the implicated supplier. Satisfying all of these at once is not automatic.

  * Mid-plan surprises are real: the batch you were about to recall turns out to
    already have a recall row; the employee you assigned is Inactive; the only
    other supplier of that material does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Schema constants — mirrored from db/schema.sql CHECK constraints
# --------------------------------------------------------------------------- #

BATCH_STATUSES = ("In Production", "Pending QA", "Approved",
                  "Rejected", "Distributed", "Recalled")

#: Reaching customers -> containment requires a Product_Recall row.
DISTRIBUTED_STATUSES = ("Distributed",)
#: Still inside the plant -> a status change to 'Rejected' is sufficient.
INTERNAL_STATUSES = ("In Production", "Pending QA", "Approved")

EMPLOYEE_ROLES = ("Researcher", "Production Staff", "QA Staff",
                  "QA Manager", "Operations Manager")
#: ONLY this role may authorize a Product_Recall. QA Staff may not.
RECALL_AUTHORIZER_ROLES = ("QA Manager",)
#: Who may own a Production_Order.
ORDER_OWNER_ROLES = ("Production Staff", "Operations Manager")

PRODUCTION_STATUSES = ("Pending", "In Progress", "Completed", "Cancelled")
RECALL_STATUSES = ("Initiated", "In Progress", "Completed")


# --------------------------------------------------------------------------- #
# Sub-task taxonomy
# --------------------------------------------------------------------------- #

class SubtaskType(str, Enum):
    """
    The shape of a sub-task, which is what planning/routing.py routes on.
    Shape -- not topic -- decides the planner.
    """

    DETERMINISTIC_LOOKUP = "deterministic_lookup"      # -> direct tool call
    SINGLE_PASS_REASONING = "single_pass_reasoning"    # -> Plan-and-Solve
    AMBIGUOUS_RANKING = "ambiguous_ranking"            # -> Tree of Thoughts
    HIGH_BRANCH_VALIDATED = "high_branch_validated"    # -> LATS (grounded)
    CHEAP_REVISABLE_TEXT = "cheap_revisable_text"      # -> Self-Refine
    WRITE_GATE = "write_gate"                          # -> validator, no LLM


@dataclass(frozen=True)
class Subtask:
    id: str
    title: str
    type: SubtaskType
    depends_on: tuple[str, ...] = ()
    instruction: str = ""

    def __post_init__(self) -> None:
        if self.id in self.depends_on:
            raise ValueError(f"Subtask {self.id!r} depends on itself")


# --------------------------------------------------------------------------- #
# The canonical DAG
# --------------------------------------------------------------------------- #
# NOTE: planning_lab.models.Plan caps tasks at 8 (max_length=8). We use 7, so
# dynamic decomposition has room for exactly one inserted node before it must
# start replacing rather than appending.

CANONICAL_SUBTASKS: tuple[Subtask, ...] = (
    Subtask(
        id="t1_trace",
        title="trace_impact",
        type=SubtaskType.DETERMINISTIC_LOOKUP,
        instruction=(
            "For the failed batch, return THREE cohorts: (a) sibling batches "
            "sharing its ProductionOrderID, (b) batches whose production order "
            "used the same SupplierID within the manufacturing window, "
            "(c) batches sharing its CurrentLocation. Include BatchID, "
            "BatchStatus, MedicineID, ManufacturingDate for each."
        ),
    ),
    Subtask(
        id="t2_scope",
        title="classify_scope",
        type=SubtaskType.AMBIGUOUS_RANKING,
        depends_on=("t1_trace",),
        instruction=(
            "Assign every batch from the trace to exactly one tier: CONTAIN, "
            "WATCH, or CLEAR, and justify each. Cohort (a) is strong evidence; "
            "(b) is material-linked; (c) is weakest. Over-containment recalls "
            "saleable product; under-containment leaves failed material with "
            "customers. Consider several tierings before committing."
        ),
    ),
    Subtask(
        id="t3_action",
        title="split_by_status",
        type=SubtaskType.SINGLE_PASS_REASONING,
        depends_on=("t2_scope",),
        instruction=(
            "Split the CONTAIN tier by BatchStatus. Batches that are "
            "'Distributed' require a Product_Recall row. Batches that are "
            "'In Production', 'Pending QA' or 'Approved' require only a "
            "BatchStatus change to 'Rejected'. Report the two lists and the "
            "total quantity affected per medicine."
        ),
    ),
    Subtask(
        id="t4_supply",
        title="assess_shortfall",
        type=SubtaskType.SINGLE_PASS_REASONING,
        depends_on=("t3_action",),
        instruction=(
            "For each medicine losing stock to containment, compute what "
            "remains unaffected and whether any open Production_Order already "
            "covers the gap. Return a shortfall figure per medicine."
        ),
    ),
    Subtask(
        id="t5_plan",
        title="plan_containment",
        type=SubtaskType.HIGH_BRANCH_VALIDATED,
        depends_on=("t4_supply",),
        instruction=(
            "Produce the full containment plan: which batches to reject, which "
            "to recall, who authorizes the recalls, and what replacement "
            "production orders to raise. Replacement orders must NOT re-source "
            "from the implicated supplier."
        ),
    ),
    Subtask(
        id="t6_notice",
        title="draft_notices",
        type=SubtaskType.CHEAP_REVISABLE_TEXT,
        depends_on=("t5_plan",),
        instruction=(
            "Draft the recall reason text and an internal QA deviation notice. "
            "Rubric: name the failed batch and its test, state the impact "
            "cohorts and why each was included or excluded, list containment "
            "actions with owners, state the replacement plan, name the "
            "authorizing QA Manager. Mark hypotheses as hypotheses."
        ),
    ),
    Subtask(
        id="t7_commit",
        title="commit",
        type=SubtaskType.WRITE_GATE,
        depends_on=("t6_notice",),
        instruction=(
            "Write the batch status changes, Product_Recall rows and "
            "replacement Production_Orders through the MCP server. Refuse if "
            "the grounded validator has not returned success."
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Request + plan payloads
# --------------------------------------------------------------------------- #

@dataclass
class DeviationRequest:
    """The real request a Vellora QA lead sends today."""

    raw_text: str
    failed_batch_id: Optional[int] = None
    #: e.g. "Sterility" — matches Quality_Test.TestType
    test_type: str = ""
    finding: str = ""

    def as_prompt(self) -> str:
        return self.raw_text


@dataclass
class ReplacementOrder:
    """One proposed Production_Order row."""

    medicine_id: int
    supplier_id: int
    planned_quantity: int
    responsible_employee_id: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReplacementOrder":
        def _int(v):
            return None if v in (None, "") else int(v)
        return cls(
            medicine_id=_int(d.get("medicine_id")),
            supplier_id=_int(d.get("supplier_id")),
            planned_quantity=_int(d.get("planned_quantity")) or 0,
            responsible_employee_id=_int(d.get("responsible_employee_id")),
        )

    def as_payload(self) -> Dict[str, Any]:
        """Shape handed to mcp_server tools / validation for the dry run."""
        return {
            "MedicineID": self.medicine_id,
            "SupplierID": self.supplier_id,
            "PlannedQuantity": self.planned_quantity,
            "ResponsibleEmployeeID": self.responsible_employee_id,
        }


@dataclass
class ContainmentPlan:
    """
    The candidate t5_plan output. This is what VelloraEnvironment.evaluate()
    validates, and therefore what LATS and Reflexion are actually scored on.
    """

    #: Internal batches -> BatchStatus becomes 'Rejected'.
    reject_batch_ids: List[int] = field(default_factory=list)
    #: Distributed batches -> need a Product_Recall row.
    recall_batch_ids: List[int] = field(default_factory=list)
    #: Must be an Active employee with Role = 'QA Manager'.
    recall_authorizer_employee_id: Optional[int] = None
    recall_reason: str = ""
    replacement_orders: List[ReplacementOrder] = field(default_factory=list)
    watch_batch_ids: List[int] = field(default_factory=list)
    rationale: str = ""

    @property
    def contained_batch_ids(self) -> List[int]:
        return sorted(set(self.reject_batch_ids) | set(self.recall_batch_ids))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ContainmentPlan":
        def _ints(key):
            return [int(x) for x in (d.get(key) or [])]
        aid = d.get("recall_authorizer_employee_id")
        return cls(
            reject_batch_ids=_ints("reject_batch_ids"),
            recall_batch_ids=_ints("recall_batch_ids"),
            recall_authorizer_employee_id=(
                None if aid in (None, "") else int(aid)),
            recall_reason=d.get("recall_reason", ""),
            replacement_orders=[ReplacementOrder.from_dict(o)
                                for o in (d.get("replacement_orders") or [])],
            watch_batch_ids=_ints("watch_batch_ids"),
            rationale=d.get("rationale", ""),
        )


#: Emitted into every t5_plan prompt so the environment can parse the candidate.
#: An unparseable candidate scores 0 and wastes a whole MCTS rollout, so keep
#: this verbatim in the prompt.
PLAN_OUTPUT_CONTRACT = """
Return your answer as a single JSON object inside a ```json fenced block, with
exactly these keys:

```json
{
  "reject_batch_ids": [<batch ids that stay inside the plant>],
  "recall_batch_ids": [<batch ids that reached customers>],
  "recall_authorizer_employee_id": <EmployeeID of an Active QA Manager>,
  "recall_reason": "<one sentence naming the failed test and the linkage>",
  "replacement_orders": [
    {
      "medicine_id": <MedicineID>,
      "supplier_id": <SupplierID, NOT the implicated one>,
      "planned_quantity": <positive integer>,
      "responsible_employee_id": <EmployeeID of Active Production Staff>
    }
  ],
  "watch_batch_ids": [<batch ids linked but not actionable>],
  "rationale": "<one short paragraph>"
}
```

Every id must come from the VALID IDS section above. Do not invent ids and do
not copy the angle-bracket placeholders.

Rules you must respect:
- Only batches with BatchStatus 'Distributed' belong in recall_batch_ids.
- Batches still inside the plant belong in reject_batch_ids.
- A batch that already has a Product_Recall row can be neither recalled again
  nor rejected; it belongs in watch_batch_ids.
- recall_authorizer_employee_id must be an Active employee whose Role is
  exactly 'QA Manager'. 'QA Staff' is a different role and is not permitted.
- replacement_orders must not use the supplier implicated in the failure.
""".strip()
