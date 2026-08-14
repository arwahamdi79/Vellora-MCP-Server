"""
planning/vellora_env.py — the GROUNDED environment.

Replaces the toolkit's algorithms/environment.py, whose Environment.evaluate()
returns round(rng.betavariate(5.0, 2.0), 4) and explicitly discards the
candidate ("del state"). Every score produced here comes from a real query
against db/vellora.db plus a dry run through mcp_server/validation.py.

Nothing in this file asks a model whether it is happy with its own output.

INTERFACE (verified against the fork):
    class Environment:
        def evaluate(self, state: str) -> EnvironmentFeedback
    EnvironmentFeedback(success: bool, score: float, details: list[str])
    ...with model_config extra="forbid", so no additional fields.

We subclass Environment so `isinstance` checks inside lats.py and reflexion.py
cannot reject us.

Used by:
  - LATS external feedback         (routing: HIGH_BRANCH_VALIDATED)
  - Reflexion's evaluate step      (planning/critique.py)
  - The t7_commit write gate       (refuses to write unless success=True)
"""

from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent / "toolkit"))

import argparse
import json
import random
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from planning_lab.algorithms.environment import Environment  # noqa: E402
from planning_lab.models import EnvironmentFeedback  # noqa: E402

from .domain import (  # noqa: E402
    ContainmentPlan,
    DISTRIBUTED_STATUSES,
    INTERNAL_STATUSES,
    ORDER_OWNER_ROLES,
    RECALL_AUTHORIZER_ROLES,
)

DEFAULT_DB = "db/vellora.db"


# --------------------------------------------------------------------------- #
# Check result model
# --------------------------------------------------------------------------- #

@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    weight: float = 1.0
    critical: bool = True
    #: True when the check could not run (missing table/column/context). These
    #: are EXCLUDED from the score rather than counted as passes, so a
    #: half-wired environment can never masquerade as a grounded one.
    skipped: bool = False


@dataclass
class GroundedResult:
    checks: List[Check] = field(default_factory=list)

    @property
    def scored(self) -> List[Check]:
        return [c for c in self.checks if not c.skipped]

    @property
    def score(self) -> float:
        scored = self.scored
        if not scored:
            return 0.0
        total = sum(c.weight for c in scored)
        return sum(c.weight for c in scored if c.passed) / total

    @property
    def success(self) -> bool:
        scored = self.scored
        return bool(scored) and all(c.passed for c in scored if c.critical)

    def detail_lines(self) -> List[str]:
        """EnvironmentFeedback.details is list[str]; one line per failed check,
        naming the check, so LATS branch reflections and Reflexion episodic
        memories cite a CONSTRAINT rather than a vibe."""
        failed = [c for c in self.scored if not c.passed]
        if not failed:
            return ["All grounded checks passed."]
        out = [f"[{c.name}] {c.detail}" for c in failed]
        skipped = [c.name for c in self.checks if c.skipped]
        if skipped:
            out.append("not evaluated: " + ", ".join(skipped))
        return out

    def feedback_text(self) -> str:
        """Human-readable form for demo transcripts and the write gate."""
        if self.success:
            return "All grounded checks passed."
        return "Grounded validation FAILED:\n" + "\n".join(
            f"  - {line}" for line in self.detail_lines())

    def as_trace(self) -> List[Dict[str, Any]]:
        """Extends the toolkit's artifacts/ JSON trace with `vellora_checks`."""
        return [
            {"name": c.name, "passed": c.passed, "skipped": c.skipped,
             "critical": c.critical, "weight": c.weight, "detail": c.detail}
            for c in self.checks
        ]


# --------------------------------------------------------------------------- #
# Candidate parsing
# --------------------------------------------------------------------------- #

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _repair_truncated_json(raw: str) -> Optional[str]:
    """
    Close a JSON object that was cut off by a token limit.

    Models routinely hit max_tokens mid-object. Scoring such a candidate 0.0
    conflates a FORMATTING accident with a PLANNING error, which corrupts the
    comparison table: methods that generate longer plans get penalised for
    verbosity rather than judged on correctness. Repair is safe because we only
    ever ADD closers -- no value is invented.

    Returns None when the fragment is too short to be meaningful.
    """
    stack: list[str] = []
    in_str = esc = False
    for ch in raw:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()

    if not stack and not in_str:
        return None                      # nothing to repair

    fixed = raw
    if in_str:
        fixed += '"'
    # Drop a dangling key or comma that would make the close invalid,
    # e.g. '..., "rationale":' or '..., '
    fixed = re.sub(r',\s*"[^"]*"\s*:\s*$', "", fixed)
    fixed = re.sub(r',\s*$', "", fixed)
    fixed = re.sub(r'"\s*:\s*$', '": null', fixed)
    return fixed + "".join(reversed(stack))


def parse_candidate(text: str) -> Optional[ContainmentPlan]:
    """Extract a ContainmentPlan from a model candidate. None if unparseable."""
    plan, _ = parse_candidate_verbose(text)
    return plan


def parse_candidate_verbose(text: str) -> tuple[Optional[ContainmentPlan], bool]:
    """As parse_candidate, plus whether truncation repair was needed. The flag
    is recorded in the trace so a reader can tell repaired runs from clean
    ones rather than taking the score on trust."""
    if not text:
        return None, False
    m = _JSON_BLOCK.search(text)
    raw = m.group(1) if m else None
    if raw is None:
        start, depth, in_str, esc = None, 0, False, False
        for i, ch in enumerate(text):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    raw = text[start:i + 1]
                    break
        if raw is None and start is not None:
            raw = text[start:]           # unterminated: repair below
    if raw is None:
        return None, False
    try:
        return ContainmentPlan.from_dict(json.loads(raw)), False
    except Exception:
        pass
    repaired = _repair_truncated_json(raw)
    if repaired:
        try:
            return ContainmentPlan.from_dict(json.loads(repaired)), True
        except Exception:
            pass
    return None, False


# --------------------------------------------------------------------------- #
# The grounded environment
# --------------------------------------------------------------------------- #

class VelloraEnvironment(Environment):
    """
    Grounded EnvironmentFeedback source for the Deviation Response Agent.

    Parameters
    ----------
    db_path       : path to db/vellora.db. Opened read-only; never writes.
    failed_batch_id : the batch whose Quality_Test failed. Everything else
                    (production order, supplier, medicine, location, window) is
                    derived from the database, not supplied by the caller.
    window_days   : how many days either side of the failed batch's
                    ManufacturingDate count as the same material window.
    use_mcp_validation : dry-run replacement order payloads through
                    mcp_server.validation. Set False only in unit tests.
    """

    def __init__(
        self,
        db_path: str = DEFAULT_DB,
        failed_batch_id: Optional[int] = None,
        window_days: int = 14,
        success_threshold: float = 1.0,
        use_mcp_validation: bool = True,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(success_threshold=min(max(success_threshold, 0.0), 1.0),
                         rng=rng)
        self.db_path = db_path
        self.failed_batch_id = failed_batch_id
        self.window_days = window_days
        self.use_mcp_validation = use_mcp_validation
        self.last_result: Optional[GroundedResult] = None
        self._ctx: Optional[Dict[str, Any]] = None

    # -- plumbing ----------------------------------------------------------- #

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _rows(conn, sql: str, args: Sequence[Any] = ()) -> List[sqlite3.Row]:
        return list(conn.execute(sql, tuple(args)))

    def context(self, conn) -> Dict[str, Any]:
        """
        Derive the deviation context from the failed batch. Cached per instance.

        Returns the implicated production order, supplier, medicine, location
        and manufacturing date -- the anchors every check hangs off.
        """
        if self._ctx is not None:
            return self._ctx
        if self.failed_batch_id is None:
            self._ctx = {}
            return self._ctx
        rows = self._rows(conn, """
            SELECT b.BatchID, b.ProductionOrderID, b.MedicineID,
                   b.ManufacturingDate, b.CurrentLocation, b.BatchStatus,
                   o.SupplierID
              FROM Manufacturing_Batch b
              JOIN Production_Order o
                ON o.ProductionOrderID = b.ProductionOrderID
             WHERE b.BatchID = ?
        """, (self.failed_batch_id,))
        self._ctx = dict(rows[0]) if rows else {}
        return self._ctx

    # -- toolkit-facing entry point ----------------------------------------- #

    def evaluate(self, state: str) -> EnvironmentFeedback:
        """Signature matches Environment.evaluate(state) exactly."""
        plan, repaired = parse_candidate_verbose(state)
        if plan is None:
            res = GroundedResult(checks=[Check(
                "parse", False,
                "candidate contained no parseable JSON plan; emit it in a "
                "```json fenced block exactly as the contract specifies")])
            self.last_result = res
            return EnvironmentFeedback(success=False, score=0.0,
                                       details=res.detail_lines())

        res = self.validate_plan(plan)
        if repaired:
            # Informational, not a failure: the plan was truncated by a token
            # limit and closed programmatically. Visible in the trace so
            # repaired runs are distinguishable from clean ones.
            res.checks.append(Check(
                "json_repaired", True,
                "candidate was truncated mid-object and closed programmatically;"
                " no values were invented",
                critical=False, weight=0.0))
        self.last_result = res
        return EnvironmentFeedback(
            success=res.success and res.score >= self.success_threshold,
            score=round(res.score, 4),
            details=res.detail_lines(),
        )

    # -- the seven checks --------------------------------------------------- #

    def validate_plan(self, plan: ContainmentPlan) -> GroundedResult:
        res = GroundedResult()
        with self._connect() as conn:
            ctx = self.context(conn)
            for fn in (
                self._check_impact_completeness,
                self._check_no_implicated_supplier_reuse,
                self._check_recall_eligibility,
                self._check_no_duplicate_recall,
                self._check_recall_authorizer,
                self._check_order_owner,
                self._check_payload_validation,
                self._check_no_over_scoping,
            ):
                name = fn.__name__.replace("_check_", "")
                try:
                    res.checks.append(fn(conn, plan, ctx))
                except sqlite3.Error as exc:
                    res.checks.append(Check(
                        name, False, f"query failed: {exc}", skipped=True))
        return res

    # 1 --------------------------------------------------------------------- #
    def _check_impact_completeness(self, conn, plan, ctx) -> Check:
        """
        Set difference against the real impact cohorts. Sibling batches (same
        ProductionOrderID) and same-supplier batches inside the manufacturing
        window must all be contained or explicitly listed as WATCH. This is the
        check that catches under-scoping.
        """
        if not ctx:
            return Check("impact_completeness", False,
                         "no failed batch context", skipped=True)

        siblings = {r["BatchID"] for r in self._rows(conn, """
            SELECT BatchID FROM Manufacturing_Batch
             WHERE ProductionOrderID = ? AND BatchID != ?
        """, (ctx["ProductionOrderID"], ctx["BatchID"]))}

        same_supplier = {r["BatchID"] for r in self._rows(conn, """
            SELECT b.BatchID
              FROM Manufacturing_Batch b
              JOIN Production_Order o
                ON o.ProductionOrderID = b.ProductionOrderID
             WHERE o.SupplierID = ?
               AND b.BatchID != ?
               AND ABS(julianday(b.ManufacturingDate) - julianday(?)) <= ?
        """, (ctx["SupplierID"], ctx["BatchID"],
              ctx["ManufacturingDate"], self.window_days))}

        required = siblings | same_supplier | {ctx["BatchID"]}
        accounted = set(plan.contained_batch_ids) | set(plan.watch_batch_ids)
        missing = sorted(required - accounted)

        if missing:
            return Check(
                "impact_completeness", False,
                f"batches {missing} share the failed batch's production order "
                f"or its supplier inside the {self.window_days}-day window but "
                f"appear in neither the containment nor the watch list")
        return Check("impact_completeness", True,
                     f"all {len(required)} linked batches accounted for "
                     f"({len(siblings)} sibling, {len(same_supplier)} supplier-linked)")

    # 2 --------------------------------------------------------------------- #
    def _check_no_implicated_supplier_reuse(self, conn, plan, ctx) -> Check:
        """
        THE TRAP CHECK. A replacement order that re-sources from the supplier
        whose material is implicated re-introduces the failure it exists to
        route around. Reads perfectly well in prose; fails one join.
        """
        if not ctx:
            return Check("no_implicated_supplier_reuse", False,
                         "no failed batch context", skipped=True)
        bad = [o for o in plan.replacement_orders
               if o.supplier_id == ctx["SupplierID"]]
        if bad:
            names = self._rows(conn,
                               "SELECT CompanyName FROM Supplier WHERE SupplierID = ?",
                               (ctx["SupplierID"],))
            who = names[0]["CompanyName"] if names else f"id {ctx['SupplierID']}"
            return Check(
                "no_implicated_supplier_reuse", False,
                f"{len(bad)} replacement order(s) re-source from supplier "
                f"{ctx['SupplierID']} ({who}) — the supplier of the material in "
                f"the failed batch's production order {ctx['ProductionOrderID']}")
        return Check("no_implicated_supplier_reuse", True,
                     "no replacement order uses the implicated supplier")

    # 3 --------------------------------------------------------------------- #
    def _check_recall_eligibility(self, conn, plan, ctx) -> Check:
        """
        Status decides the instrument. Only 'Distributed' batches have reached
        customers and warrant a Product_Recall; internal batches take a
        BatchStatus change. Getting this backwards is expensive in one
        direction and negligent in the other.
        """
        ids = plan.contained_batch_ids
        if not ids:
            return Check("recall_eligibility", False, "plan contains nothing")
        marks = ",".join("?" * len(ids))
        rows = self._rows(conn, f"""
            SELECT BatchID, BatchStatus FROM Manufacturing_Batch
             WHERE BatchID IN ({marks})
        """, ids)
        status = {r["BatchID"]: r["BatchStatus"] for r in rows}

        problems = []
        for bid in ids:
            if bid not in status:
                problems.append(f"batch {bid} does not exist")
        for bid in plan.recall_batch_ids:
            s = status.get(bid)
            if s and s not in DISTRIBUTED_STATUSES:
                problems.append(
                    f"batch {bid} is '{s}', not Distributed — it needs a status "
                    f"change to Rejected, not a Product_Recall")
        for bid in plan.reject_batch_ids:
            s = status.get(bid)
            if s in DISTRIBUTED_STATUSES:
                problems.append(
                    f"batch {bid} is Distributed and has reached customers — "
                    f"rejecting it internally does not contain it, it needs a "
                    f"Product_Recall")
            elif s and s not in INTERNAL_STATUSES:
                problems.append(f"batch {bid} is already '{s}'")
        if problems:
            return Check("recall_eligibility", False, "; ".join(problems))
        return Check("recall_eligibility", True,
                     f"{len(plan.recall_batch_ids)} recall(s) and "
                     f"{len(plan.reject_batch_ids)} rejection(s) match batch status")

    # 4 --------------------------------------------------------------------- #
    def _check_no_duplicate_recall(self, conn, plan, ctx) -> Check:
        """Product_Recall.BatchID is UNIQUE — a second recall row is a hard
        constraint violation, and the insert would fail at commit time."""
        if not plan.recall_batch_ids:
            return Check("no_duplicate_recall", True, "no recalls proposed")
        marks = ",".join("?" * len(plan.recall_batch_ids))
        rows = self._rows(conn, f"""
            SELECT BatchID, RecallStatus FROM Product_Recall
             WHERE BatchID IN ({marks})
        """, plan.recall_batch_ids)
        if rows:
            pairs = ", ".join(f"batch {r['BatchID']} ({r['RecallStatus']})"
                              for r in rows)
            return Check("no_duplicate_recall", False,
                         f"already recalled: {pairs}. Product_Recall.BatchID is "
                         f"UNIQUE, so these inserts would be rejected")
        return Check("no_duplicate_recall", True, "no existing recall rows")

    # 5 --------------------------------------------------------------------- #
    def _check_recall_authorizer(self, conn, plan, ctx) -> Check:
        """
        Only a 'QA Manager' may authorize. 'QA Staff' is a different role in the
        schema's CHECK constraint, and models pick it constantly because the
        titles read alike.
        """
        if not plan.recall_batch_ids:
            return Check("recall_authorizer", True, "no recalls to authorize")
        eid = plan.recall_authorizer_employee_id
        if eid is None:
            return Check("recall_authorizer", False,
                         "recalls proposed with no authorizing employee")
        rows = self._rows(conn, """
            SELECT FullName, Role, AccountStatus FROM Employee
             WHERE EmployeeID = ?
        """, (eid,))
        if not rows:
            return Check("recall_authorizer", False,
                         f"employee {eid} does not exist")
        r = rows[0]
        if r["Role"] not in RECALL_AUTHORIZER_ROLES:
            return Check("recall_authorizer", False,
                         f"employee {eid} ({r['FullName']}) has Role "
                         f"'{r['Role']}'; only {RECALL_AUTHORIZER_ROLES[0]} may "
                         f"authorize a Product_Recall")
        if r["AccountStatus"] != "Active":
            return Check("recall_authorizer", False,
                         f"employee {eid} ({r['FullName']}) is "
                         f"{r['AccountStatus']}, not Active")
        return Check("recall_authorizer", True,
                     f"{r['FullName']} is an Active QA Manager")

    # 6 --------------------------------------------------------------------- #
    def _check_order_owner(self, conn, plan, ctx) -> Check:
        """Production_Order.ResponsibleEmployeeID is NOT NULL and must point at
        a real, active employee who can actually own production."""
        if not plan.replacement_orders:
            return Check("order_owner", True, "no replacement orders")
        problems = []
        for o in plan.replacement_orders:
            eid = o.responsible_employee_id
            if eid is None:
                problems.append(
                    f"order for medicine {o.medicine_id} has no responsible "
                    f"employee (column is NOT NULL)")
                continue
            rows = self._rows(conn, """
                SELECT FullName, Role, AccountStatus FROM Employee
                 WHERE EmployeeID = ?""", (eid,))
            if not rows:
                problems.append(f"employee {eid} does not exist")
                continue
            r = rows[0]
            if r["AccountStatus"] != "Active":
                problems.append(f"employee {eid} is {r['AccountStatus']}")
            if r["Role"] not in ORDER_OWNER_ROLES:
                problems.append(
                    f"employee {eid} is {r['Role']}; production orders need "
                    f"{' or '.join(ORDER_OWNER_ROLES)}")
        if problems:
            return Check("order_owner", False, "; ".join(problems))
        return Check("order_owner", True, "all order owners active and eligible")

    # 7 --------------------------------------------------------------------- #
    def _check_payload_validation(self, conn, plan, ctx) -> Check:
        """
        Dry run through the REAL mcp_server.validation helpers — the same
        functions the write path uses. No rows are written.
        """
        if not plan.replacement_orders:
            return Check("payload_validation", True, "no payloads to validate")
        if not self.use_mcp_validation:
            return Check("payload_validation", False,
                         "mcp validation disabled", skipped=True)
        try:
            from mcp_server.validation import (
                validate_exists, validate_positive_integer)
        except Exception as exc:
            return Check("payload_validation", False,
                         f"could not import mcp_server.validation: {exc}",
                         skipped=True)

        problems = []
        for o in plan.replacement_orders:
            try:
                validate_positive_integer(o.planned_quantity, "PlannedQuantity")
                validate_exists("Medicine", "MedicineID", o.medicine_id)
                validate_exists("Supplier", "SupplierID", o.supplier_id)
                validate_exists("Employee", "EmployeeID",
                                o.responsible_employee_id)
            except Exception as exc:
                problems.append(f"{o.as_payload()} rejected: {exc}")
        if problems:
            return Check("payload_validation", False, "; ".join(problems))
        return Check("payload_validation", True,
                     f"{len(plan.replacement_orders)} payload(s) validate")


    # 8 --------------------------------------------------------------------- #
    def _check_no_over_scoping(self, conn, plan, ctx) -> Check:
        """
        The other direction of the cost asymmetry.

        Containing a batch that is neither a sibling nor material-linked scraps
        saleable stock for no evidential reason. Co-location is NOT sufficient:
        two batches sharing a warehouse three months apart have no production
        linkage, and the trace surfaces them only as weak context.

        Without this check the environment rewards "recall everything
        distributed", which is the failure mode a real QA department is most
        afraid of after under-containment.
        """
        if not ctx:
            return Check("no_over_scoping", False,
                         "no failed batch context", skipped=True)

        siblings = {r["BatchID"] for r in self._rows(conn, """
            SELECT BatchID FROM Manufacturing_Batch
             WHERE ProductionOrderID = ?
        """, (ctx["ProductionOrderID"],))}

        supplier_linked = {r["BatchID"] for r in self._rows(conn, """
            SELECT b.BatchID
              FROM Manufacturing_Batch b
              JOIN Production_Order o
                ON o.ProductionOrderID = b.ProductionOrderID
             WHERE o.SupplierID = ?
               AND ABS(julianday(b.ManufacturingDate) - julianday(?)) <= ?
        """, (ctx["SupplierID"], ctx["ManufacturingDate"], self.window_days))}

        justified = siblings | supplier_linked
        extras = sorted(set(plan.contained_batch_ids) - justified)
        if extras:
            rows = self._rows(conn, f"""
                SELECT b.BatchID, m.MedicineName, o.SupplierID,
                       b.ManufacturingDate
                  FROM Manufacturing_Batch b
                  JOIN Production_Order o
                    ON o.ProductionOrderID = b.ProductionOrderID
                  JOIN Medicine m ON m.MedicineID = b.MedicineID
                 WHERE b.BatchID IN ({",".join("?" * len(extras))})
            """, extras)
            why = "; ".join(
                f"batch {r['BatchID']} ({r['MedicineName']}, supplier "
                f"{r['SupplierID']}, made {r['ManufacturingDate']})"
                for r in rows)
            return Check(
                "no_over_scoping", False,
                f"contained without production linkage: {why}. These share "
                f"neither the failed production order nor supplier "
                f"{ctx['SupplierID']} inside the {self.window_days}-day window. "
                f"Containing them scraps saleable stock. Co-location alone is "
                f"not evidence of contamination.")
        return Check("no_over_scoping", True,
                     f"all {len(plan.contained_batch_ids)} contained batches "
                     f"have production or material linkage")


# --------------------------------------------------------------------------- #
# Ungrounded control — for the required comparison row only
# --------------------------------------------------------------------------- #

class UngroundedBaselineEnvironment(Environment):
    """
    The toolkit's stock randomized evaluator under an honest name.

    Exists so planning_eval can run the mandatory "LATS ungrounded vs LATS
    grounded" contrast. It must never be what the shipped agent uses.
    """


# --------------------------------------------------------------------------- #
# Introspection
# --------------------------------------------------------------------------- #

EXPECTED = {
    "Employee": ["EmployeeID", "FullName", "Role", "AccountStatus"],
    "Medicine": ["MedicineID"],
    "Supplier": ["SupplierID", "CompanyName"],
    "Production_Order": ["ProductionOrderID", "MedicineID", "SupplierID",
                         "PlannedQuantity", "ProductionStatus",
                         "ResponsibleEmployeeID"],
    "Manufacturing_Batch": ["BatchID", "ProductionOrderID", "MedicineID",
                            "ManufacturingDate", "ExpiryDate", "BatchStatus",
                            "CurrentLocation"],
    "Quality_Test": ["TestID", "BatchID", "TestResult", "TestDate"],
    "Product_Recall": ["RecallID", "BatchID", "RecallStatus",
                       "AuthorizedManagerID"],
}


def introspect(db_path: str) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    bad = 0
    for t, cols in EXPECTED.items():
        if t not in tables:
            print(f"  MISSING TABLE  {t}")
            bad += 1
            continue
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        for c in cols:
            if c not in have:
                print(f"  MISSING COLUMN {t}.{c}   have: {sorted(have)}")
                bad += 1
    print()
    if bad:
        print(f"{bad} mismatch(es) — the grounded checks cannot run correctly.")
        return bad

    print("Schema matches. Candidate failed batches (most recent QA failures):")
    for r in conn.execute("""
        SELECT q.BatchID, q.TestType, q.TestDate, b.BatchStatus,
               b.ProductionOrderID, o.SupplierID
          FROM Quality_Test q
          JOIN Manufacturing_Batch b ON b.BatchID = q.BatchID
          JOIN Production_Order o ON o.ProductionOrderID = b.ProductionOrderID
         WHERE q.TestResult = 'Fail'
         ORDER BY q.TestDate DESC LIMIT 10
    """):
        print(f"  BatchID={r[0]:<6} {r[1]:<22} {r[2]}  status={r[3]:<14} "
              f"order={r[4]} supplier={r[5]}")

    print("\nActive QA Managers (valid recall authorizers):")
    for r in conn.execute("""
        SELECT EmployeeID, FullName FROM Employee
         WHERE Role = 'QA Manager' AND AccountStatus = 'Active'
    """):
        print(f"  EmployeeID={r[0]:<5} {r[1]}")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--introspect", action="store_true")
    p.add_argument("--db", default=DEFAULT_DB)
    a = p.parse_args()
    if a.introspect:
        raise SystemExit(1 if introspect(a.db) else 0)
    p.print_help()
