"""
planning_eval/test_grounding.py — proof that the grounded environment works.

Run:  pytest planning_eval/test_grounding.py -v

These tests need NO API key and cost nothing: they exercise
VelloraEnvironment.evaluate() directly against db/vellora.db. Run them before
every scored evaluation. If they fail, the comparison table is meaningless,
because the reward signal LATS and Reflexion are optimising against is broken.

Each test corresponds to one trap in db/seed_deviation.sql, and to one row of
the grounded-vs-ungrounded evidence in the README.
"""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from planning.vellora_env import (
    UngroundedBaselineEnvironment,
    VelloraEnvironment,
    parse_candidate,
)
from planning_eval.test_suite import (
    EXPECTED_RECALL,
    EXPECTED_REJECT,
    EXPECTED_UNTOUCHED,
    EXPECTED_WATCH,
    FAILED_BATCH_ID,
    VALID_AUTHORIZER_ID,
)

DB = os.environ.get("VELLORA_DB", "db/vellora.db")


def _plan(**overrides) -> str:
    """The correct containment plan, with fields overridable per test."""
    base = {
        "recall_batch_ids": list(EXPECTED_RECALL),
        "reject_batch_ids": list(EXPECTED_REJECT),
        "watch_batch_ids": list(EXPECTED_WATCH),
        "recall_authorizer_employee_id": VALID_AUTHORIZER_ID,
        "recall_reason": "Sterility test failure traced to the raw material "
                         "intake shared by these production orders.",
        "replacement_orders": [
            {"medicine_id": 4, "supplier_id": 2, "planned_quantity": 6000,
             "responsible_employee_id": _active_production_staff()},
            {"medicine_id": 6, "supplier_id": 4, "planned_quantity": 4000,
             "responsible_employee_id": _active_production_staff()},
        ],
        "rationale": "Recall distributed stock, reject internal stock, watch "
                     "the already-recalled batch, re-source elsewhere.",
    }
    base.update(overrides)
    return "```json\n" + json.dumps(base) + "\n```"


def _q(sql, args=()):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return list(conn.execute(sql, args))
    finally:
        conn.close()


def _active_production_staff() -> int:
    rows = _q("""SELECT EmployeeID FROM Employee
                  WHERE Role = 'Production Staff' AND AccountStatus = 'Active'
                  ORDER BY EmployeeID LIMIT 1""")
    return rows[0][0]


def _inactive_production_staff() -> int:
    rows = _q("""SELECT EmployeeID FROM Employee
                  WHERE Role = 'Production Staff' AND AccountStatus = 'Inactive'
                  ORDER BY EmployeeID LIMIT 1""")
    return rows[0][0]


def _active_qa_staff() -> int:
    rows = _q("""SELECT EmployeeID FROM Employee
                  WHERE Role = 'QA Staff' AND AccountStatus = 'Active'
                  ORDER BY EmployeeID LIMIT 1""")
    return rows[0][0]


@pytest.fixture
def env():
    return VelloraEnvironment(db_path=DB, failed_batch_id=FAILED_BATCH_ID,
                              use_mcp_validation=False)


def _failed(fb) -> str:
    return " ".join(fb.details)


# --------------------------------------------------------------------------- #
# Preconditions
# --------------------------------------------------------------------------- #

def test_seed_is_applied():
    """db/seed_deviation.sql must have been run, or every case is stale."""
    rows = _q("""SELECT b.BatchStatus FROM Quality_Test q
                   JOIN Manufacturing_Batch b ON b.BatchID = q.BatchID
                  WHERE q.BatchID = ? AND q.TestResult = 'Fail'""",
              (FAILED_BATCH_ID,))
    assert rows, "batch 21 has no failed test; run db/seed_deviation.sql"
    assert rows[0][0] == "Distributed", (
        "batch 21 is no longer Distributed. Someone containment-ed it, or the "
        "seed ran twice. Restore db/vellora.db.bak and re-seed.")


def test_correct_plan_passes():
    """The known-good plan must score 1.0, or the checks are over-strict."""
    e = VelloraEnvironment(db_path=DB, failed_batch_id=FAILED_BATCH_ID,
                           use_mcp_validation=False)
    fb = e.evaluate(_plan())
    assert fb.success, _failed(fb)
    assert fb.score == 1.0


# --------------------------------------------------------------------------- #
# One test per trap
# --------------------------------------------------------------------------- #

def test_catches_implicated_supplier_reuse(env):
    """THE SHOWCASE (GRD-01). Re-ordering from the implicated supplier."""
    fb = env.evaluate(_plan(replacement_orders=[
        {"medicine_id": 4, "supplier_id": 1, "planned_quantity": 6000,
         "responsible_employee_id": _active_production_staff()}]))
    assert not fb.success
    assert "no_implicated_supplier_reuse" in _failed(fb)


def test_catches_qa_staff_as_authorizer(env):
    """GRD-02. Only Role='QA Manager' may authorize a Product_Recall."""
    fb = env.evaluate(_plan(recall_authorizer_employee_id=_active_qa_staff()))
    assert not fb.success
    assert "recall_authorizer" in _failed(fb)


def test_catches_duplicate_recall(env):
    """GRD-03. Product_Recall.BatchID is UNIQUE; batch 25 already has a row."""
    fb = env.evaluate(_plan(
        recall_batch_ids=EXPECTED_RECALL + EXPECTED_WATCH,
        watch_batch_ids=[]))
    assert not fb.success
    assert "no_duplicate_recall" in _failed(fb)


def test_catches_inactive_order_owner(env):
    """GRD-04. AccountStatus is invisible in prose, one query in SQL."""
    fb = env.evaluate(_plan(replacement_orders=[
        {"medicine_id": 4, "supplier_id": 2, "planned_quantity": 6000,
         "responsible_employee_id": _inactive_production_staff()}]))
    assert not fb.success
    assert "order_owner" in _failed(fb)


def test_catches_under_scoping(env):
    """Missing the supplier-linked cohort — scoping to the failed order only."""
    fb = env.evaluate(_plan(recall_batch_ids=[FAILED_BATCH_ID],
                            watch_batch_ids=[]))
    assert not fb.success
    assert "impact_completeness" in _failed(fb)


def test_catches_recalling_an_internal_batch(env):
    """Batch 22 is Approved, never distributed. A recall is the wrong
    instrument and expensive."""
    fb = env.evaluate(_plan(
        recall_batch_ids=EXPECTED_RECALL + EXPECTED_REJECT,
        reject_batch_ids=[]))
    assert not fb.success
    assert "recall_eligibility" in _failed(fb)


def test_catches_rejecting_a_distributed_batch(env):
    """Batch 23 reached customers. An internal rejection does not contain it."""
    fb = env.evaluate(_plan(recall_batch_ids=[FAILED_BATCH_ID],
                            reject_batch_ids=EXPECTED_REJECT + [23]))
    assert not fb.success
    assert "recall_eligibility" in _failed(fb)


def test_unparseable_candidate_scores_zero(env):
    """LATS rollouts that emit prose instead of JSON must not score well."""
    fb = env.evaluate("I would recall the affected batches and notify QA.")
    assert not fb.success
    assert fb.score == 0.0


# --------------------------------------------------------------------------- #
# The over-scoping control
# --------------------------------------------------------------------------- #

def test_control_batch_is_not_required():
    """
    Batch 24 shares the medicine and the week but not the supplier. The
    environment must NOT demand it — otherwise the agent is rewarded for
    scrapping saleable stock and the whole cost asymmetry collapses.
    """
    e = VelloraEnvironment(db_path=DB, failed_batch_id=FAILED_BATCH_ID,
                           use_mcp_validation=False)
    fb = e.evaluate(_plan())
    assert fb.success, _failed(fb)
    for bid in EXPECTED_UNTOUCHED:
        assert str(bid) not in _failed(fb)


# --------------------------------------------------------------------------- #
# Grounded vs ungrounded — the contrast the rubric requires
# --------------------------------------------------------------------------- #

def test_ungrounded_environment_ignores_the_candidate():
    """
    Evidence for the README: the toolkit default returns the same distribution
    of scores for a correct plan and for gibberish, because it discards the
    candidate entirely. This is why an ungrounded LATS is expensive theatre.
    """
    import random
    good = UngroundedBaselineEnvironment(rng=random.Random(0)).evaluate(_plan())
    junk = UngroundedBaselineEnvironment(rng=random.Random(0)).evaluate("asdf")
    assert good.score == junk.score


def test_grounded_environment_distinguishes_them():
    e1 = VelloraEnvironment(db_path=DB, failed_batch_id=FAILED_BATCH_ID,
                            use_mcp_validation=False)
    e2 = VelloraEnvironment(db_path=DB, failed_batch_id=FAILED_BATCH_ID,
                            use_mcp_validation=False)
    assert e1.evaluate(_plan()).score > e2.evaluate("asdf").score


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("wrapper", [
    "{body}",
    "Here is my plan:\n```json\n{body}\n```\nLet me know.",
    "```\n{body}\n```",
    "Preamble text {body} trailing text",
])
def test_parser_tolerates_wrapping(wrapper):
    body = json.dumps({"recall_batch_ids": [21], "reject_batch_ids": [22]})
    plan = parse_candidate(wrapper.format(body=body))
    assert plan is not None
    assert plan.recall_batch_ids == [21]
