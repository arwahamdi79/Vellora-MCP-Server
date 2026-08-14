"""
planning_eval/test_suite.py — the FIXED test suite.

=============================================================================
FROZEN. Do not edit after the first scored run.
=============================================================================
Changing cases between runs invalidates the comparison table, and the lab
guardrails call that out explicitly. If you genuinely need more coverage,
append to SUITE_V2 and report it as a separate table.

Every id below is REAL, verified against db/vellora.db after
db/seed_deviation.sql was applied:

  Batch 21  Ibuprex 400,  order 17, supplier 1, mfg 2026-07-25, Distributed
            -> FAILED Sterility Test 2026-08-10          [the deviation]
  Batch 22  Ibuprex 400,  order 17, supplier 1, mfg 2026-07-26, Approved
            -> sibling cohort, internal      -> reject
  Batch 23  Loratadex,    order 18, supplier 1, mfg 2026-07-28, Distributed
            -> supplier cohort, with customers -> recall
  Batch 24  Ibuprex 400,  order 19, supplier 2, mfg 2026-07-27, Distributed
            -> CONTROL. Same medicine and week, different material.
               Containing it is over-scoping.
  Batch 25  Loratadex,    order 20, supplier 1, mfg 2026-07-29, Recalled
            -> already has Product_Recall row 4. UNIQUE constraint means it
               can be neither recalled again nor rejected -> WATCH only.

  Employee 7   Dina Farouk  QA Manager        Active  [only valid authorizer]
  Employees with Role 'QA Staff'              Active  [tempting but invalid]
  One Production Staff member is              Inactive [invalid order owner]

Tags
----
DEC-DYNAMIC   : an early observation invalidates a static plan
DEC-STATIC    : fully mechanical, no surprises -> favours decomposition-first
PLN-LOOKAHEAD : needs search; a greedy first pass commits to a bad answer
PLN-SIMPLE    : single pass; ToT/LATS are wasted spend
GRD           : grounded validator catches what self-critique waves through
RFX           : failures stack; one retry is not enough
SRF           : rubric-checkable prose; one critique+revision suffices
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Ground truth for the seeded deviation. The grader script scores against this;
# VelloraEnvironment derives its own cohorts independently from the database,
# so this is a cross-check, not the source of truth.
# --------------------------------------------------------------------------- #

FAILED_BATCH_ID = 21
IMPLICATED_SUPPLIER_ID = 1
WINDOW_DAYS = 14

EXPECTED_RECALL = [21, 23]      # Distributed -> Product_Recall required
EXPECTED_REJECT = [22]          # internal    -> BatchStatus 'Rejected'
EXPECTED_WATCH = [25]           # already recalled, UNIQUE blocks a second row
EXPECTED_UNTOUCHED = [24]       # supplier 2 -> over-scoping if contained
VALID_AUTHORIZER_ID = 7         # Dina Farouk, the only Active QA Manager
FORBIDDEN_SUPPLIER_ID = 1       # replacement orders must avoid this


@dataclass(frozen=True)
class Case:
    id: str
    tag: str
    prompt: str
    #: Kwargs for VelloraEnvironment. Usually just the failed batch.
    env_kwargs: Dict[str, Any] = field(default_factory=dict)
    #: What "task success" means. Checked by planning_eval/run_matrix.py.
    success_criteria: str = ""
    #: Sub-task id from domain.CANONICAL_SUBTASKS when the case targets one.
    target_subtask: Optional[str] = None


SUITE: List[Case] = [

    # ================================================================= DEC-DYNAMIC
    # Cases where the first observation changes what the remaining plan should be.
    Case(
        id="DEC-DYNAMIC-01",
        tag="DEC-DYNAMIC",
        prompt=(
            "Batch 21 just failed its sterility test and it's already out with "
            "customers. Contain this properly."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "The trace reveals the failure is material-linked, not order-linked, "
            "which pulls in batch 23 from a DIFFERENT production order. A static "
            "plan written before the trace ran scopes to order 17 only and "
            "leaves batch 23 with customers."
        ),
    ),
    Case(
        id="DEC-DYNAMIC-02",
        tag="DEC-DYNAMIC",
        prompt=(
            "We have a sterility failure on batch 21. Work out the blast radius "
            "and recall whatever needs recalling."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "'Recall whatever needs recalling' is a trap: batch 25 is already "
            "recalled and batch 22 was never distributed. Only after observing "
            "each batch's status can the agent know that only two of the four "
            "linked batches take a recall."
        ),
    ),
    Case(
        id="DEC-DYNAMIC-03",
        tag="DEC-DYNAMIC",
        prompt=(
            "Batch 21 failed QA. Contain it and raise replacement production "
            "so we don't run short on Ibuprex 400."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "The replacement plan cannot be written until the trace identifies "
            "supplier 1 as implicated. A static plan routinely re-orders from "
            "the same supplier because that is where the medicine came from."
        ),
    ),
    Case(
        id="DEC-DYNAMIC-04",
        tag="DEC-DYNAMIC",
        prompt=(
            "Sterility excursion on batch 21. Assume the worst about the raw "
            "material and tell me what we have to pull."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "'Assume the worst' invites over-scoping onto batch 24, which shares "
            "the medicine and the week but not the supplier. Dynamic "
            "decomposition should discover the supplier split and stop there."
        ),
    ),

    # ================================================================== DEC-STATIC
    # Mechanical sweeps. Dynamic decomposition should cost more for no gain.
    Case(
        id="DEC-STATIC-01",
        tag="DEC-STATIC",
        prompt=(
            "List every batch currently in 'Pending QA' with its medicine, "
            "production order and the QA staff member who last tested it."
        ),
        success_criteria="Correct enumeration; no branch points exist.",
    ),
    Case(
        id="DEC-STATIC-02",
        tag="DEC-STATIC",
        prompt=(
            "Produce a QA summary: pass/fail counts per test type, and the list "
            "of batches with any failed test."
        ),
        success_criteria="Correct aggregates. Static and dynamic should agree exactly.",
    ),
    Case(
        id="DEC-STATIC-03",
        tag="DEC-STATIC",
        prompt=(
            "Which batches expire within the next 12 months, and what is their "
            "current status and location?"
        ),
        success_criteria="Deterministic date filter.",
    ),
    Case(
        id="DEC-STATIC-04",
        tag="DEC-STATIC",
        prompt=(
            "For every open Product_Recall, report the batch, the medicine, the "
            "authorizing manager and how many days the recall has been running."
        ),
        success_criteria="Straight join; no ambiguity.",
    ),

    # =============================================================== PLN-LOOKAHEAD
    # Several defensible answers; a greedy first pass picks a worse one.
    Case(
        id="PLN-LOOKAHEAD-01",
        tag="PLN-LOOKAHEAD",
        target_subtask="t2_scope",
        prompt=(
            "Batch 21 failed sterility. Tier every linked batch as CONTAIN, "
            "WATCH or CLEAR. We cannot afford to scrap saleable stock, and we "
            "cannot leave suspect material with customers."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "The two constraints pull opposite ways. Correct tiering puts 21 and "
            "23 in CONTAIN, 25 in WATCH, and leaves 24 CLEAR. A single pass "
            "usually either sweeps in 24 or drops 23."
        ),
    ),
    Case(
        id="PLN-LOOKAHEAD-02",
        tag="PLN-LOOKAHEAD",
        target_subtask="t5_plan",
        prompt=(
            "Give me the full containment plan for the batch 21 sterility "
            "failure, including replacement production orders."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "Six independent decisions: recall set, reject set, watch set, "
            "authorizer, replacement suppliers, order owners. Each is separately "
            "wrong-able and the grounded validator scores all six."
        ),
    ),
    Case(
        id="PLN-LOOKAHEAD-03",
        tag="PLN-LOOKAHEAD",
        target_subtask="t5_plan",
        prompt=(
            "Contain batch 21's failure, but keep the recall as narrow as the "
            "evidence honestly allows."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "'As narrow as honest' rewards search: dropping batch 23 is cheaper "
            "and wrong; keeping batch 24 is safer and wasteful."
        ),
    ),
    Case(
        id="PLN-LOOKAHEAD-04",
        tag="PLN-LOOKAHEAD",
        target_subtask="t5_plan",
        prompt=(
            "Batch 21 failed. Contain it and replace the lost Ibuprex 400 and "
            "Loratadex stock, choosing suppliers we can actually trust here."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "Two replacement orders, neither from supplier 1, each owned by an "
            "Active Production Staff member."
        ),
    ),

    # ================================================================== PLN-SIMPLE
    # One pass is enough. ToT/LATS should show cost with no accuracy gain.
    Case(
        id="PLN-SIMPLE-01",
        tag="PLN-SIMPLE",
        target_subtask="t3_action",
        prompt=(
            "Batches 21, 22, 23 and 25 are all implicated. Which need a "
            "Product_Recall and which only need a status change, and why?"
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria="Status lookup plus a rule. 21 and 23 recall, 22 reject, 25 neither.",
    ),
    Case(
        id="PLN-SIMPLE-02",
        tag="PLN-SIMPLE",
        target_subtask="t4_supply",
        prompt=(
            "If we contain batches 21, 22 and 23, how much Ibuprex 400 and "
            "Loratadex stock remains unaffected?"
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria="Correct arithmetic over remaining batches.",
    ),
    Case(
        id="PLN-SIMPLE-03",
        tag="PLN-SIMPLE",
        target_subtask="t3_action",
        prompt="Who is authorised to sign off a product recall here, and why only them?",
        success_criteria="Names Dina Farouk (7); explains QA Staff is a distinct role.",
    ),

    # ========================================================================= GRD
    # The grounded validator catches what a self-critic approves.
    Case(
        id="GRD-01",
        tag="GRD",
        target_subtask="t5_plan",
        prompt=(
            "Batch 21 failed sterility. Contain the affected stock and raise "
            "replacement production for Ibuprex 400."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "THE SHOWCASE. The natural plan re-orders Ibuprex 400 from supplier "
            "1 -- the supplier whose material is implicated -- because that is "
            "where the medicine has always come from. It reads as competent QA "
            "reasoning and a self-critic approves it. "
            "no_implicated_supplier_reuse rejects it on one join. Capture the "
            "ungrounded and grounded traces side by side."
        ),
    ),
    Case(
        id="GRD-02",
        tag="GRD",
        target_subtask="t5_plan",
        prompt=(
            "Contain batch 21's failure and get the recall signed off by whoever "
            "is on QA."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "'Whoever is on QA' pulls the model toward a QA Staff member. Only "
            "Role = 'QA Manager' may authorize; recall_authorizer catches it."
        ),
    ),
    Case(
        id="GRD-03",
        tag="GRD",
        target_subtask="t5_plan",
        prompt=(
            "Batch 21 failed. Recall everything that came off the same raw "
            "material and is still with customers."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "Batch 25 matches that description in prose but already carries "
            "Product_Recall row 4. no_duplicate_recall catches the second "
            "insert, which the UNIQUE constraint would reject at commit time."
        ),
    ),
    Case(
        id="GRD-04",
        tag="GRD",
        target_subtask="t5_plan",
        prompt=(
            "Contain batch 21 and assign someone to own the replacement "
            "production order."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "One Production Staff member is Inactive. The employee list reads "
            "identically to a model; order_owner checks AccountStatus."
        ),
    ),

    # ========================================================================= RFX
    # Failures stack; a single retry fixes only the first.
    Case(
        id="RFX-01",
        tag="RFX",
        target_subtask="t5_plan",
        prompt=(
            "Produce a containment plan for batch 21 that will pass QA "
            "validation on submission. It has to be right first time."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "STACKED FAILURES. Typical trajectory: trial 1 fails "
            "no_implicated_supplier_reuse, trial 2 fixes the supplier but fails "
            "recall_authorizer, trial 3 succeeds only with BOTH reflections in "
            "the buffer. Re-run with memory_size=0 to show it re-breaks the "
            "first constraint."
        ),
    ),
    Case(
        id="RFX-02",
        tag="RFX",
        target_subtask="t5_plan",
        prompt=(
            "Contain batch 21 completely: nothing suspect left with customers, "
            "nothing saleable scrapped, every write legal against the schema."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "Three constraint classes (completeness, eligibility, authority) "
            "fail in sequence across trials."
        ),
    ),
    Case(
        id="RFX-03",
        tag="RFX",
        target_subtask="t5_plan",
        prompt=(
            "Batch 21 failed sterility. Give me a plan I can execute today with "
            "no follow-up questions."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "Requires carrying forward which suppliers and which employees were "
            "already ruled out by earlier trials."
        ),
    ),

    # ========================================================================= SRF
    # Prose against a rubric. One critique and revision should be enough.
    Case(
        id="SRF-01",
        tag="SRF",
        target_subtask="t6_notice",
        prompt=(
            "Write the RecallReason text for batch 21's product recall. It goes "
            "into the Product_Recall table and is read by regulators."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "Rubric: names the batch and the failed test, states the material "
            "linkage, marks root cause as a hypothesis, fits the 500-char "
            "column. First drafts usually state the cause as established fact."
        ),
    ),
    Case(
        id="SRF-02",
        tag="SRF",
        target_subtask="t6_notice",
        prompt=(
            "Draft the internal QA deviation notice for the batch 21 sterility "
            "failure."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "Rubric: impact cohorts with inclusion AND exclusion reasoning "
            "(why 24 was excluded), containment actions with owners, "
            "replacement plan, authorizing QA Manager named."
        ),
    ),
    Case(
        id="SRF-03",
        tag="SRF",
        target_subtask="t6_notice",
        prompt=(
            "Write the customer notification for the recalled Ibuprex 400 and "
            "Loratadex batches. Do not speculate about root cause."
        ),
        env_kwargs={"failed_batch_id": 21},
        success_criteria=(
            "The 'do not speculate' constraint is what the critique must catch; "
            "first drafts almost always name a suspected cause."
        ),
    ),
]


def by_tag(tag: str) -> List[Case]:
    return [c for c in SUITE if c.tag == tag]


def by_id(case_id: str) -> Case:
    for c in SUITE:
        if c.id == case_id:
            return c
    raise KeyError(case_id)


def by_subtask(subtask_id: str) -> List[Case]:
    return [c for c in SUITE if c.target_subtask == subtask_id]


if __name__ == "__main__":
    from collections import Counter
    print(f"{len(SUITE)} cases (FROZEN)\n")
    for tag, n in sorted(Counter(c.tag for c in SUITE).items()):
        print(f"  {tag:15s} {n}")
    print("\ntargeted sub-tasks:")
    for st, n in sorted(Counter(c.target_subtask for c in SUITE
                                if c.target_subtask).items()):
        print(f"  {st:15s} {n}")
