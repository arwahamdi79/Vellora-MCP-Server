"""
planning_eval/test_suite.py — the FIXED test suite.

FREEZE THIS FILE before the first scored run. Changing cases between runs
invalidates the comparison table, and the guardrails call that out explicitly.
Commit it, then only ever append to a `v2` list if you genuinely need more.

Every case is a real request shape a Vellora production planner sends. Each is
tagged with the contrast it exists to expose, so a grader can see the suite was
designed to *discriminate* between methods rather than to make one look good.

Tags
----
DEC-DYNAMIC   : early observation invalidates a static plan -> favours dynamic
DEC-STATIC    : fully mechanical, no surprises -> favours decomposition-first
PLN-LOOKAHEAD : needs search; PS commits to a bad first plan
PLN-SIMPLE    : single pass; ToT/LATS are waste
GRD           : grounded critic catches what self-critique waves through
RFX           : failures stack; one retry is not enough
SRF           : rubric-checkable prose; one critique+revision suffices
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Case:
    id: str
    tag: str
    prompt: str
    #: Deviation context handed to VelloraEnvironment (T1 normally derives this;
    #: fixed here so scoring is reproducible across methods).
    context: Dict[str, Any] = field(default_factory=dict)
    #: What "task success" means for this case. Checked by the grader script.
    success_criteria: str = ""
    #: Sub-task this case is scored on, when it targets one node.
    target_subtask: Optional[str] = None


# Replace the ids/lots/dates below with real rows from your seeded vellora.db
# BEFORE freezing. A case pointing at a batch that doesn't exist scores 0 for
# every method and tells you nothing.

SUITE: List[Case] = [

    # ---------------------------------------------------------------- DEC-DYNAMIC
    Case(
        id="DEC-DYNAMIC-01",
        tag="DEC-DYNAMIC",
        prompt=(
            "Batch 1042 failed QA — contamination detected on Line 3. Contain it "
            "and keep the Medicine 12 commitment on schedule."
        ),
        context={
            "failed_batch_id": 1042, "implicated_line_id": 3,
            "suspect_supplier_lot": "SL-4471", "suspect_supplier_id": 4,
            "window_start": "2026-08-01", "window_end": "2026-08-13",
        },
        success_criteria=(
            "Plan quarantines the supplier-lot cohort on Line 5 as well as the "
            "Line 3 cohort. Decomposition-first is expected to miss it because "
            "its static plan was written before T1 returned."
        ),
    ),
    Case(
        id="DEC-DYNAMIC-02",
        tag="DEC-DYNAMIC",
        prompt=(
            "Line 7 tripped a temperature excursion overnight. Work out what's "
            "affected and re-plan this week's production so nothing ships out of spec."
        ),
        context={"implicated_line_id": 7,
                 "window_start": "2026-08-10", "window_end": "2026-08-13"},
        success_criteria="Recovery re-plans after discovering Line 7 is still on hold.",
    ),
    Case(
        id="DEC-DYNAMIC-03",
        tag="DEC-DYNAMIC",
        prompt=(
            "Supplier 4's latest raw-material lot came back out of specification. "
            "Find every batch that used it and sort out the fallout."
        ),
        context={"suspect_supplier_id": 4, "suspect_supplier_lot": "SL-4471"},
        success_criteria="Cohort spans multiple lines; plan adapts to that.",
    ),
    Case(
        id="DEC-DYNAMIC-04",
        tag="DEC-DYNAMIC",
        prompt=(
            "Batch 998 just failed its stability re-test. Contain it, and if the "
            "replacement can't be produced before the customer need-by date, tell "
            "me what the options are."
        ),
        context={"failed_batch_id": 998},
        success_criteria=(
            "Agent discovers the shortfall is unrecoverable in time and switches "
            "to producing options rather than executing a stale recovery plan."
        ),
    ),

    # ----------------------------------------------------------------- DEC-STATIC
    Case(
        id="DEC-STATIC-01",
        tag="DEC-STATIC",
        prompt=(
            "Schedule the 60-day stability re-tests for every batch expiring in "
            "the next two months and assign a QA owner to each."
        ),
        success_criteria="All due batches scheduled; no surprises mid-plan.",
    ),
    Case(
        id="DEC-STATIC-02",
        tag="DEC-STATIC",
        prompt=(
            "Produce this month's QA summary: pass/fail counts per line, per "
            "medicine, and the list of open deviations."
        ),
        success_criteria="Correct aggregates; static plan should match dynamic exactly.",
    ),
    Case(
        id="DEC-STATIC-03",
        tag="DEC-STATIC",
        prompt=(
            "Close out deviation records for every batch released more than 30 "
            "days ago with no open quality test."
        ),
        success_criteria="Mechanical sweep; dynamic decomposition should cost more for the same result.",
    ),
    Case(
        id="DEC-STATIC-04",
        tag="DEC-STATIC",
        prompt=(
            "List every production order confirmed for next week with its line, "
            "supplier and QA approver, and flag any missing an approver."
        ),
        success_criteria="Deterministic; no branch points.",
    ),

    # -------------------------------------------------------------- PLN-LOOKAHEAD
    Case(
        id="PLN-LOOKAHEAD-01",
        tag="PLN-LOOKAHEAD",
        target_subtask="T4",
        prompt=(
            "Three medicines are short after the Line 3 quarantine and only two "
            "lines are free before the need-by dates. Propose the production "
            "sequence that breaks the fewest commitments."
        ),
        context={"implicated_line_id": 3, "suspect_supplier_lot": "SL-4471",
                 "suspect_supplier_id": 4},
        success_criteria=(
            "A greedy first-fit ordering breaks a commitment that a searched "
            "ordering does not. PS is expected to commit to the greedy one."
        ),
    ),
    Case(
        id="PLN-LOOKAHEAD-02",
        tag="PLN-LOOKAHEAD",
        target_subtask="T4",
        prompt=(
            "Recover the Medicine 12 shortfall without using Line 3 or Supplier "
            "4's suspect lot, and without pushing any existing confirmed order "
            "past its end date."
        ),
        context={"implicated_line_id": 3, "suspect_supplier_lot": "SL-4471",
                 "suspect_supplier_id": 4},
        success_criteria="All three constraints simultaneously satisfied.",
    ),
    Case(
        id="PLN-LOOKAHEAD-03",
        tag="PLN-LOOKAHEAD",
        target_subtask="T2",
        prompt=(
            "Twelve batches touch the Line 3 window or the suspect lot. Tier them "
            "QUARANTINE / WATCH / CLEAR so we scrap as little saleable stock as "
            "possible without leaving a contaminated batch in the CLEAR tier."
        ),
        context={"implicated_line_id": 3, "suspect_supplier_lot": "SL-4471"},
        success_criteria="No implicated batch lands in CLEAR; WATCH tier used to limit scrap.",
    ),
    Case(
        id="PLN-LOOKAHEAD-04",
        tag="PLN-LOOKAHEAD",
        target_subtask="T4",
        prompt=(
            "Split the Medicine 12 recovery across two lines if that lets us hit "
            "the need-by date; otherwise keep it on one and tell me what slips."
        ),
        context={"implicated_line_id": 3, "suspect_supplier_id": 4},
        success_criteria="Correctly evaluates both branches rather than assuming one.",
    ),

    # ----------------------------------------------------------------- PLN-SIMPLE
    Case(
        id="PLN-SIMPLE-01",
        tag="PLN-SIMPLE",
        target_subtask="T3",
        prompt=(
            "After quarantining batches 1042, 1043 and 1051, how much uncommitted "
            "Medicine 12 stock is left and when does the first commitment break?"
        ),
        success_criteria="Correct arithmetic; ToT/LATS should add cost and no accuracy.",
    ),
    Case(
        id="PLN-SIMPLE-02",
        tag="PLN-SIMPLE",
        target_subtask="T3",
        prompt="Total quantity currently on QA hold, broken down by medicine.",
        success_criteria="Correct aggregate.",
    ),
    Case(
        id="PLN-SIMPLE-03",
        tag="PLN-SIMPLE",
        target_subtask="T3",
        prompt=(
            "If Supplier 4 needs 12 days lead time, what is the latest date we "
            "can place the Medicine 12 replacement order and still hit Sept 2?"
        ),
        success_criteria="Single date, correct.",
    ),

    # ------------------------------------------------------------------------ GRD
    Case(
        id="GRD-01",
        tag="GRD",
        target_subtask="T4",
        prompt=(
            "Propose the Medicine 12 replacement order to cover the Batch 1042 "
            "quarantine. Line 7 is free."
        ),
        context={"failed_batch_id": 1042, "implicated_line_id": 3,
                 "suspect_supplier_lot": "SL-4471", "suspect_supplier_id": 4,
                 "window_start": "2026-08-01", "window_end": "2026-08-13"},
        success_criteria=(
            "THE SHOWCASE CASE. The natural plan (Medicine 12 / Line 7 / qty 5000 "
            "/ Supplier 4) passes every surface check and the self-critic "
            "approves it. no_suspect_lot_reuse fails: Supplier 4's lot SL-4471 is "
            "the lot under investigation. Capture both traces."
        ),
    ),
    Case(
        id="GRD-02",
        tag="GRD",
        target_subtask="T4",
        prompt="Recover the Batch 998 shortfall on the soonest available line.",
        context={"failed_batch_id": 998, "implicated_line_id": 5,
                 "window_start": "2026-08-05", "window_end": "2026-08-13"},
        success_criteria=(
            "'Soonest available' tempts the model onto a line that is free today "
            "but on a cleaning hold; line_availability catches it."
        ),
    ),
    Case(
        id="GRD-03",
        tag="GRD",
        target_subtask="T4",
        prompt=(
            "Quarantine the Line 3 batches and get the replacement order approved "
            "by whoever's on QA today."
        ),
        context={"implicated_line_id": 3,
                 "window_start": "2026-08-01", "window_end": "2026-08-13"},
        success_criteria=(
            "Model picks a plausible-sounding employee; approver_valid checks the "
            "role and Active status against the employees table."
        ),
    ),

    # ------------------------------------------------------------------------ RFX
    Case(
        id="RFX-01",
        tag="RFX",
        target_subtask="T4",
        prompt=(
            "Produce a compliant replacement plan for the Batch 1042 quarantine. "
            "It has to pass QA validation on submission."
        ),
        context={"failed_batch_id": 1042, "implicated_line_id": 3,
                 "suspect_supplier_lot": "SL-4471", "suspect_supplier_id": 4,
                 "window_start": "2026-08-01", "window_end": "2026-08-13"},
        success_criteria=(
            "STACKED FAILURES. Trial 1 fails line_availability, trial 2 fails "
            "supplier_lead_time, trial 3 succeeds only with BOTH reflections in "
            "the buffer. Re-run with memory_size=0 to show it re-breaks."
        ),
    ),
    Case(
        id="RFX-02",
        tag="RFX",
        target_subtask="T4",
        prompt=(
            "Re-plan the whole week's production around the Line 3 hold. Every "
            "confirmed order must still land inside its window."
        ),
        context={"implicated_line_id": 3},
        success_criteria="Multiple constraint classes fail across trials.",
    ),
    Case(
        id="RFX-03",
        tag="RFX",
        target_subtask="T4",
        prompt=(
            "Cover all three shortfalls from the supplier-lot recall using only "
            "lines that are free and suppliers that aren't under investigation."
        ),
        context={"suspect_supplier_id": 4, "suspect_supplier_lot": "SL-4471"},
        success_criteria="Requires carrying forward which lines/suppliers were already ruled out.",
    ),

    # ------------------------------------------------------------------------ SRF
    Case(
        id="SRF-01",
        tag="SRF",
        target_subtask="T5",
        prompt=(
            "Draft the internal QA hold notice for the Batch 1042 deviation."
        ),
        success_criteria=(
            "Rubric: batch ids, root-cause hypothesis marked as hypothesis, scope "
            "+ justification, containment actions with owners, recovery plan, "
            "approver. First draft typically omits owners or states the "
            "hypothesis as fact."
        ),
    ),
    Case(
        id="SRF-02",
        tag="SRF",
        target_subtask="T5",
        prompt="Write the regulatory deviation summary for the same event.",
        success_criteria="Rubric fields all present; no speculation stated as fact.",
    ),
    Case(
        id="SRF-03",
        tag="SRF",
        target_subtask="T5",
        prompt=(
            "Write the customer notification for the two orders delayed by the "
            "quarantine. Don't disclose the contamination detail."
        ),
        success_criteria=(
            "Critique must catch disclosure of internal detail -- a constraint "
            "the first draft usually violates."
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


if __name__ == "__main__":
    from collections import Counter
    print(f"{len(SUITE)} cases")
    for tag, n in sorted(Counter(c.tag for c in SUITE).items()):
        print(f"  {tag:15s} {n}")
