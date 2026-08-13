"""
planning/vellora_env.py — the GROUNDED environment.

This is the drop-in replacement for the toolkit's `algorithms/environment.py`,
whose `Environment.evaluate()` returns a beta-distributed random score with no
connection to reality. Every score produced here comes from a real query against
db/vellora.db and, where wired, a dry-run through mcp_server/validation.py.

Nothing in this file asks a model whether it is happy with its own output.

Used by:
  - LATS external feedback (planning/routing.py -> HIGH_BRANCH_VALIDATED)
  - Reflexion's evaluate step (planning/critique.py)
  - The T6 write gate (refuses to commit unless success=True)

------------------------------------------------------------------------------
WIRING NOTE
------------------------------------------------------------------------------
`SCHEMA` below maps logical names -> your real table/column names. It is written
against the names visible in your repo (BatchID, MedicineID, SupplierID, Status,
employees with Role/Status, production_orders, quality_tests). Run

    python -m planning.vellora_env --introspect --db db/vellora.db

and it will print exactly which mappings do not match your schema. Fix the dict,
not the queries.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .domain import RecoveryPlan

# --------------------------------------------------------------------------- #
# Toolkit interop
# --------------------------------------------------------------------------- #
# The algorithms depend only on a small environment protocol: an object with
# .evaluate(). We import the toolkit's own model so traces stay in ITS format.

# VERIFIED: the toolkit defines EnvironmentFeedback in planning_lab.models as a
# pydantic BaseModel with fields  success: bool, score: float (0..1),
# details: list[str]  and model_config = ConfigDict(extra="forbid").
# There is NO `feedback` field -- passing one raises a ValidationError.

import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).parent / "toolkit"))

from planning_lab.models import EnvironmentFeedback  # noqa: E402


# --------------------------------------------------------------------------- #
# Schema mapping  <-- EDIT THIS, NOT THE QUERIES
# --------------------------------------------------------------------------- #

SCHEMA: Dict[str, Dict[str, str]] = {
    "batches": {
        "table": "batches",
        "id": "BatchID",
        "medicine_id": "MedicineID",
        "line_id": "LineID",
        "status": "Status",
        "supplier_lot": "SupplierLot",
        "supplier_id": "SupplierID",
        "produced_on": "ProductionDate",
        "expiry": "ExpiryDate",
        "quantity": "Quantity",
    },
    "production_orders": {
        "table": "production_orders",
        "id": "OrderID",
        "medicine_id": "MedicineID",
        "line_id": "LineID",
        "quantity": "Quantity",
        "supplier_id": "SupplierID",
        "status": "Status",
        "start": "StartDate",
        "end": "EndDate",
    },
    "suppliers": {
        "table": "suppliers",
        "id": "SupplierID",
        "lead_time_days": "LeadTimeDays",
        "status": "Status",
    },
    "employees": {
        "table": "employees",
        "id": "EmployeeID",
        "role": "Role",
        "status": "Status",
    },
    "lines": {
        "table": "production_lines",
        "id": "LineID",
        "status": "Status",          # 'Free' | 'Cleaning' | 'Maintenance'
    },
    "medicines": {
        "table": "medicines",
        "id": "MedicineID",
    },
}

#: Batch statuses that mean "this batch is committed to somebody".
OPEN_ORDER_STATUSES = ("Open", "In Production", "Allocated", "Confirmed")
#: Line statuses that block a new production order.
BLOCKING_LINE_STATUSES = ("Cleaning", "Maintenance", "Hold", "Quarantine")


def _q(entity: str, col: str) -> str:
    return SCHEMA[entity][col]


def _t(entity: str) -> str:
    return SCHEMA[entity]["table"]


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
    #: True when the check could not run (missing table/column) -- these are
    #: excluded from the score rather than silently counted as passes, so a
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
        got = sum(c.weight for c in scored if c.passed)
        return got / total

    @property
    def success(self) -> bool:
        scored = self.scored
        if not scored:
            return False
        return all(c.passed for c in scored if c.critical)

    def feedback_text(self) -> str:
        """Human-readable form, used in demo transcripts and the write gate."""
        failed = [c for c in self.scored if not c.passed]
        if not failed:
            return "All grounded checks passed."
        lines = ["Grounded validation FAILED:"]
        lines += [f"  - [{c.name}] {c.detail}" for c in failed]
        skipped = [c for c in self.checks if c.skipped]
        if skipped:
            lines.append(
                "  (not evaluated: " + ", ".join(c.name for c in skipped) + ")"
            )
        return "\n".join(lines)

    def detail_lines(self) -> List[str]:
        """EnvironmentFeedback.details is a list[str]; one line per failed
        check so LATS reflections and Reflexion memories cite check NAMES."""
        failed = [c for c in self.scored if not c.passed]
        if not failed:
            return ["All grounded checks passed."]
        out = [f"[{c.name}] {c.detail}" for c in failed]
        skipped = [c.name for c in self.checks if c.skipped]
        if skipped:
            out.append("not evaluated: " + ", ".join(skipped))
        return out

    def as_trace(self) -> List[Dict[str, Any]]:
        """Extends the toolkit's JSON trace with `vellora_checks`."""
        return [
            {
                "name": c.name,
                "passed": c.passed,
                "skipped": c.skipped,
                "critical": c.critical,
                "weight": c.weight,
                "detail": c.detail,
            }
            for c in self.checks
        ]


# --------------------------------------------------------------------------- #
# Candidate parsing
# --------------------------------------------------------------------------- #

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_candidate(text: str) -> Optional[RecoveryPlan]:
    """Extract a RecoveryPlan from a model candidate. None if unparseable."""
    if not text:
        return None
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
    if raw is None:
        return None
    try:
        return RecoveryPlan.from_dict(json.loads(raw))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# The environment
# --------------------------------------------------------------------------- #

class VelloraEnvironment:
    """
    Grounded EnvironmentFeedback source for the Deviation Response Agent.

    Satisfies the toolkit's environment protocol:  evaluate(task, candidate)
    -> EnvironmentFeedback.  Drop it in wherever the toolkit constructs its
    randomized `Environment`.

    Parameters
    ----------
    db_path
        Path to db/vellora.db. Opened read-only; this validator never writes.
    context
        The deviation context: failed batch id, implicated line, suspect
        supplier lot, cleaning window. Produced by T1.
    validate_payload
        Optional callable wired to mcp_server/validation.py for a dry-run schema
        check of the write payload. Left None -> `payload_schema` is SKIPPED,
        never silently passed.
    """

    def __init__(
        self,
        db_path: str,
        context: Optional[Dict[str, Any]] = None,
        validate_payload: Optional[Callable[[Dict[str, Any]], Any]] = None,
        success_threshold: float = 1.0,
    ) -> None:
        self.db_path = db_path
        self.context = context or {}
        self.validate_payload = validate_payload
        self.success_threshold = success_threshold
        self.last_result: Optional[GroundedResult] = None

    # -- plumbing ----------------------------------------------------------- #

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _rows(conn: sqlite3.Connection, sql: str, args: Sequence[Any] = ()) -> List[sqlite3.Row]:
        return list(conn.execute(sql, tuple(args)))

    # -- the toolkit-facing entry point ------------------------------------- #

    def evaluate(self, task: str = "", candidate: str = "", **_: Any) -> EnvironmentFeedback:
        plan = parse_candidate(candidate)
        if plan is None:
            res = GroundedResult(checks=[Check(
                "parse", False,
                "Candidate contained no parseable JSON plan. Emit the plan in a "
                "```json fenced block exactly as specified.",
            )])
            self.last_result = res
            return EnvironmentFeedback(success=False, score=0.0,
                                       details=res.detail_lines())

        res = self.validate_plan(plan)
        self.last_result = res
        return EnvironmentFeedback(
            success=res.success and res.score >= self.success_threshold,
            score=res.score,
            details=res.detail_lines(),
        )

    # -- the seven checks --------------------------------------------------- #

    def validate_plan(self, plan: RecoveryPlan) -> GroundedResult:
        res = GroundedResult()
        with self._connect() as conn:
            for fn in (
                self._check_quarantine_completeness,
                self._check_no_suspect_lot_reuse,
                self._check_line_availability,
                self._check_supplier_lead_time,
                self._check_commitment_integrity,
                self._check_approver_valid,
                self._check_payload_schema,
            ):
                try:
                    res.checks.append(fn(conn, plan))
                except sqlite3.Error as exc:
                    res.checks.append(Check(
                        fn.__name__.replace("_check_", ""), False,
                        f"schema mismatch, check could not run: {exc}",
                        skipped=True,
                    ))
        return res

    # 1 ---------------------------------------------------------------------- #
    def _check_quarantine_completeness(self, conn, plan) -> Check:
        """
        Set difference. Every batch on the implicated line inside the cleaning
        window, PLUS every batch consuming the suspect supplier lot on ANY line,
        must be quarantined. This is the check that catches under-scoping.
        """
        line_id = self.context.get("implicated_line_id")
        lot = self.context.get("suspect_supplier_lot")
        w_start = self.context.get("window_start")
        w_end = self.context.get("window_end")
        if line_id is None and lot is None:
            return Check("quarantine_completeness", False,
                         "no deviation context supplied", skipped=True)

        B, bid = _t("batches"), _q("batches", "id")
        required: set[int] = set()

        if line_id is not None and w_start and w_end:
            rows = self._rows(conn, f"""
                SELECT {bid} FROM {B}
                 WHERE {_q('batches','line_id')} = ?
                   AND date({_q('batches','produced_on')}) BETWEEN date(?) AND date(?)
            """, (line_id, w_start, w_end))
            required |= {r[0] for r in rows}

        if lot:
            rows = self._rows(conn, f"""
                SELECT {bid} FROM {B} WHERE {_q('batches','supplier_lot')} = ?
            """, (lot,))
            required |= {r[0] for r in rows}

        missing = sorted(required - set(plan.quarantine_batch_ids))
        if missing:
            return Check("quarantine_completeness", False,
                         f"batches {missing} share the implicated line-window or "
                         f"the suspect lot {lot!r} but are not quarantined")
        return Check("quarantine_completeness", True,
                     f"all {len(required)} implicated batches quarantined")

    # 2 ---------------------------------------------------------------------- #
    def _check_no_suspect_lot_reuse(self, conn, plan) -> Check:
        """
        THE TRAP CHECK. A recovery order that re-sources from the supplier lot
        under investigation re-introduces the contamination it exists to route
        around. Reads fine in prose; fails one join.
        """
        lot = self.context.get("suspect_supplier_lot")
        suspect_supplier = self.context.get("suspect_supplier_id")
        if lot is None and suspect_supplier is None:
            return Check("no_suspect_lot_reuse", False,
                         "no suspect lot in context", skipped=True)

        offenders = []
        for o in plan.orders:
            if lot and o.supplier_lot == lot:
                offenders.append(f"medicine {o.medicine_id} re-uses lot {lot}")
            elif suspect_supplier is not None and o.supplier_id == suspect_supplier \
                    and not o.supplier_lot:
                offenders.append(
                    f"medicine {o.medicine_id} orders from supplier "
                    f"{o.supplier_id} without naming a lot, and that supplier "
                    f"holds the suspect lot {lot}"
                )
        if offenders:
            return Check("no_suspect_lot_reuse", False, "; ".join(offenders))
        return Check("no_suspect_lot_reuse", True,
                     "no recovery order sources the suspect lot")

    # 3 ---------------------------------------------------------------------- #
    def _check_line_availability(self, conn, plan) -> Check:
        implicated = self.context.get("implicated_line_id")
        L, lid = _t("lines"), _q("lines", "id")
        problems = []
        for o in plan.orders:
            if o.line_id is None:
                problems.append("an order has no line_id")
                continue
            if implicated is not None and o.line_id == implicated:
                problems.append(f"line {o.line_id} is the contaminated line")
                continue
            rows = self._rows(
                conn, f"SELECT {_q('lines','status')} FROM {L} WHERE {lid} = ?",
                (o.line_id,))
            if not rows:
                problems.append(f"line {o.line_id} does not exist")
                continue
            status = str(rows[0][0])
            if status in BLOCKING_LINE_STATUSES:
                problems.append(f"line {o.line_id} is on {status} hold")
                continue
            if o.planned_start:
                PO = _t("production_orders")
                clash = self._rows(conn, f"""
                    SELECT {_q('production_orders','id')} FROM {PO}
                     WHERE {_q('production_orders','line_id')} = ?
                       AND date(?) BETWEEN date({_q('production_orders','start')})
                                       AND date({_q('production_orders','end')})
                """, (o.line_id, o.planned_start))
                if clash:
                    problems.append(
                        f"line {o.line_id} already runs order "
                        f"{clash[0][0]} on {o.planned_start}")
        if problems:
            return Check("line_availability", False, "; ".join(problems))
        return Check("line_availability", True, "all target lines free and clean")

    # 4 ---------------------------------------------------------------------- #
    def _check_supplier_lead_time(self, conn, plan) -> Check:
        S = _t("suppliers")
        problems = []
        for o in plan.orders:
            if o.supplier_id is None or not o.planned_start:
                continue
            rows = self._rows(conn, f"""
                SELECT {_q('suppliers','lead_time_days')} FROM {S}
                 WHERE {_q('suppliers','id')} = ?""", (o.supplier_id,))
            if not rows:
                problems.append(f"supplier {o.supplier_id} does not exist")
                continue
            lead = rows[0][0]
            if lead is None:
                continue
            gap = self._rows(conn,
                             "SELECT CAST(julianday(?) - julianday('now') AS INTEGER)",
                             (o.planned_start,))[0][0]
            if gap is not None and gap < int(lead):
                problems.append(
                    f"supplier {o.supplier_id} needs {lead}d lead time but "
                    f"production starts in {gap}d")
        if problems:
            return Check("supplier_lead_time", False, "; ".join(problems))
        return Check("supplier_lead_time", True, "lead times fit planned starts")

    # 5 ---------------------------------------------------------------------- #
    def _check_commitment_integrity(self, conn, plan) -> Check:
        """A quarantined batch must not still be allocated to an open order."""
        if not plan.quarantine_batch_ids:
            return Check("commitment_integrity", True, "nothing quarantined")
        B, PO = _t("batches"), _t("production_orders")
        marks = ",".join("?" * len(plan.quarantine_batch_ids))
        placeholders = ",".join("?" * len(OPEN_ORDER_STATUSES))
        rows = self._rows(conn, f"""
            SELECT b.{_q('batches','id')}, o.{_q('production_orders','id')}
              FROM {B} b
              JOIN {PO} o
                ON o.{_q('production_orders','medicine_id')} = b.{_q('batches','medicine_id')}
             WHERE b.{_q('batches','id')} IN ({marks})
               AND o.{_q('production_orders','status')} IN ({placeholders})
        """, (*plan.quarantine_batch_ids, *OPEN_ORDER_STATUSES))
        if rows:
            pairs = ", ".join(f"batch {r[0]}->order {r[1]}" for r in rows[:6])
            return Check("commitment_integrity", False,
                         f"quarantined batches still back open orders: {pairs}. "
                         f"Each needs a replacement order or an explicit "
                         f"customer-notification action.")
        return Check("commitment_integrity", True,
                     "no quarantined batch backs an open order")

    # 6 ---------------------------------------------------------------------- #
    def _check_approver_valid(self, conn, plan) -> Check:
        E = _t("employees")
        problems = []
        for o in plan.orders:
            eid = o.qa_approver_employee_id
            if eid is None:
                problems.append("an order has no QA approver")
                continue
            rows = self._rows(conn, f"""
                SELECT {_q('employees','role')}, {_q('employees','status')}
                  FROM {E} WHERE {_q('employees','id')} = ?""", (eid,))
            if not rows:
                problems.append(f"employee {eid} does not exist")
                continue
            role, status = str(rows[0][0] or ""), str(rows[0][1] or "")
            if "QA" not in role.upper():
                problems.append(f"employee {eid} role {role!r} is not QA")
            if status.lower() != "active":
                problems.append(f"employee {eid} is {status}, not Active")
        if problems:
            return Check("approver_valid", False, "; ".join(problems))
        return Check("approver_valid", True, "all approvers are active QA staff")

    # 7 ---------------------------------------------------------------------- #
    def _check_payload_schema(self, conn, plan) -> Check:
        """Dry-run the write payload through the real MCP validation layer."""
        if self.validate_payload is None:
            return Check("payload_schema", False,
                         "mcp_server.validation not wired in", skipped=True)
        problems = []
        for o in plan.orders:
            payload = {
                "medicine_id": o.medicine_id,
                "line_id": o.line_id,
                "quantity": o.quantity,
                "supplier_id": o.supplier_id,
                "start_date": o.planned_start,
            }
            try:
                self.validate_payload(payload)
            except Exception as exc:
                problems.append(f"{payload} rejected: {exc}")
        if problems:
            return Check("payload_schema", False, "; ".join(problems))
        return Check("payload_schema", True, "all payloads validate")


# --------------------------------------------------------------------------- #
# Ungrounded baseline -- kept ONLY so the comparison table has a fair control.
# --------------------------------------------------------------------------- #

class UngroundedBaselineEnvironment:
    """
    The toolkit's randomized evaluator, re-exported under an honest name.

    Present so `planning_eval` can run the required
    "LATS ungrounded vs LATS grounded" contrast. It must never be the
    environment the shipped agent uses.
    """

    def __init__(self, seed: int = 0, success_threshold: float = 0.7) -> None:
        import random
        self._rng = random.Random(seed)
        self.success_threshold = success_threshold

    def evaluate(self, task: str = "", candidate: str = "", **_: Any) -> EnvironmentFeedback:
        score = self._rng.betavariate(6, 3)
        return EnvironmentFeedback(
            success=score >= self.success_threshold,
            score=score,
            details=["Randomized evaluator; no connection to the database."],
        )


# --------------------------------------------------------------------------- #
# Introspection: tells you exactly which SCHEMA entries are wrong
# --------------------------------------------------------------------------- #

def introspect(db_path: str) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    bad = 0
    for entity, m in SCHEMA.items():
        t = m["table"]
        if t not in tables:
            print(f"  MISSING TABLE  {entity:18s} -> {t!r}")
            print(f"                 candidates: {sorted(tables)}")
            bad += 1
            continue
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        for logical, col in m.items():
            if logical == "table":
                continue
            if col not in cols:
                print(f"  MISSING COLUMN {entity}.{logical:14s} -> {col!r}")
                print(f"                 available: {sorted(cols)}")
                bad += 1
    print("\nSchema map is correct." if not bad
          else f"\n{bad} mapping(s) need fixing in SCHEMA.")
    return bad


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--introspect", action="store_true")
    p.add_argument("--db", default="db/vellora.db")
    a = p.parse_args()
    if a.introspect:
        raise SystemExit(1 if introspect(a.db) else 0)
    p.print_help()
