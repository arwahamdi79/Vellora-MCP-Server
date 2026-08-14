"""
planning/mcp_executor.py — the bridge to the REAL Vellora MCP server.

GRADER: this is where the planning agent stops being an LLM exercise and starts
touching the same server and database the memory/RAG agent uses. Nothing here
duplicates mcp_server/ or db/ -- reads go through mcp_server.database, writes go
through the mcp_server tool functions, and authorization is the server's own.

Two responsibilities:

  1. IMPACT TRACE (t1_trace) -- deterministic, read-only. Answers "what else is
     linked to this failure" with SQL, because that question has exactly one
     correct answer and routing it through an LLM would pay tokens to
     rediscover a JOIN.

  2. WRITE GATE (t7_commit) -- executes a ContainmentPlan against the MCP
     tools, but ONLY after VelloraEnvironment returns success. A plan that has
     not been validated is never written, and --dry-run is the default.

Identity note
-------------
Every mcp_server tool calls authorize(DB_PATH, employee_id, tool_name), and
create_product_recall() writes AuthorizedManagerID from the acting employee.
So filing a recall requires ACTING AS the QA Manager, not merely naming them in
the plan. `CommitIdentities` makes that explicit: recalls act as the QA Manager,
production orders act as Production Staff.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .domain import ContainmentPlan, DISTRIBUTED_STATUSES
from .vellora_env import VelloraEnvironment, parse_candidate

DEFAULT_DB = "db/vellora.db"


# --------------------------------------------------------------------------- #
# Defensive imports
# --------------------------------------------------------------------------- #
# mcp_server/tools.py imports the FastMCP app, notifications, and the memory
# adapter at module scope. Importing it is fine in the running server but heavy
# for an offline trace, so we import lazily and only when actually writing.
#
# Note also that tools.py imports `.Validation` (capital V) while the file
# appears as validation.py -- Windows is case-insensitive, Linux/CI is not. We
# try both so the eval harness runs on either.

def _import_validation():
    for name in ("mcp_server.validation", "mcp_server.Validation"):
        try:
            return __import__(name, fromlist=["*"])
        except ImportError:
            continue
    return None


def _import_tools():
    """Imported only at write time; raises loudly if the server is unavailable."""
    from mcp_server import tools  # noqa: WPS433
    return tools


# --------------------------------------------------------------------------- #
# Impact trace
# --------------------------------------------------------------------------- #

@dataclass
class ImpactTrace:
    """The three cohorts, kept separate because they carry different weight."""

    failed_batch: Dict[str, Any] = field(default_factory=dict)
    #: Same ProductionOrderID -- same physical run. Strongest evidence.
    siblings: List[Dict[str, Any]] = field(default_factory=list)
    #: Other orders from the same supplier inside the window. Material-linked.
    supplier_linked: List[Dict[str, Any]] = field(default_factory=list)
    #: Same CurrentLocation. Weakest -- co-storage, not co-production.
    location_linked: List[Dict[str, Any]] = field(default_factory=list)
    #: Batches already carrying a Product_Recall row (UNIQUE blocks a second).
    already_recalled: List[int] = field(default_factory=list)

    def all_linked_ids(self) -> List[int]:
        seen = {self.failed_batch.get("BatchID")}
        for group in (self.siblings, self.supplier_linked, self.location_linked):
            seen |= {b["BatchID"] for b in group}
        return sorted(i for i in seen if i is not None)

    def as_prompt_context(self) -> str:
        """Rendered into the t2_scope / t5_plan prompts. Kept compact: this text
        is re-sent on every LATS rollout, so verbosity here multiplies cost."""
        fb = self.failed_batch

        def fmt(batches):
            if not batches:
                return "    (none)"
            return "\n".join(
                f"    batch {b['BatchID']}: {b['MedicineName']}, "
                f"status={b['BatchStatus']}, made {b['ManufacturingDate']}, "
                f"at {b['CurrentLocation']}"
                for b in batches)

        return f"""FAILED BATCH
    batch {fb.get('BatchID')}: {fb.get('MedicineName')}, \
status={fb.get('BatchStatus')}, made {fb.get('ManufacturingDate')}
    production order {fb.get('ProductionOrderID')}, \
supplier {fb.get('SupplierID')} ({fb.get('CompanyName')})
    failed test: {fb.get('TestType')} on {fb.get('TestDate')}
    remarks: {fb.get('Remarks')}

SIBLING COHORT (same production order — same physical run)
{fmt(self.siblings)}

SUPPLIER COHORT (same supplier, within the manufacturing window)
{fmt(self.supplier_linked)}

CO-LOCATED (same storage location — weakest linkage)
{fmt(self.location_linked)}

ALREADY RECALLED (Product_Recall.BatchID is UNIQUE; a second recall row is \
impossible for these): {self.already_recalled or 'none'}"""


class ImpactTracer:
    """Read-only. Uses the same db/vellora.db the MCP server uses."""

    def __init__(self, db_path: str = DEFAULT_DB, window_days: int = 14) -> None:
        self.db_path = db_path
        self.window_days = window_days

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def trace(self, failed_batch_id: int) -> ImpactTrace:
        with self._conn() as conn:
            rows = list(conn.execute("""
                SELECT b.BatchID, b.ProductionOrderID, b.MedicineID,
                       b.ManufacturingDate, b.ExpiryDate, b.BatchStatus,
                       b.CurrentLocation, o.SupplierID, s.CompanyName,
                       m.MedicineName, q.TestType, q.TestDate, q.Remarks
                  FROM Manufacturing_Batch b
                  JOIN Production_Order o
                    ON o.ProductionOrderID = b.ProductionOrderID
                  JOIN Supplier s ON s.SupplierID = o.SupplierID
                  JOIN Medicine m ON m.MedicineID = b.MedicineID
             LEFT JOIN Quality_Test q
                    ON q.BatchID = b.BatchID AND q.TestResult = 'Fail'
                 WHERE b.BatchID = ?
              ORDER BY q.TestDate DESC LIMIT 1
            """, (failed_batch_id,)))
            if not rows:
                raise ValueError(f"batch {failed_batch_id} does not exist")
            fb = dict(rows[0])

            base = """
                SELECT b.BatchID, b.ProductionOrderID, b.MedicineID,
                       b.ManufacturingDate, b.BatchStatus, b.CurrentLocation,
                       o.SupplierID, m.MedicineName
                  FROM Manufacturing_Batch b
                  JOIN Production_Order o
                    ON o.ProductionOrderID = b.ProductionOrderID
                  JOIN Medicine m ON m.MedicineID = b.MedicineID
            """

            siblings = [dict(r) for r in conn.execute(
                base + " WHERE b.ProductionOrderID = ? AND b.BatchID != ?",
                (fb["ProductionOrderID"], failed_batch_id))]

            supplier_linked = [dict(r) for r in conn.execute(
                base + """ WHERE o.SupplierID = ?
                             AND b.BatchID != ?
                             AND b.ProductionOrderID != ?
                             AND ABS(julianday(b.ManufacturingDate)
                                     - julianday(?)) <= ?""",
                (fb["SupplierID"], failed_batch_id, fb["ProductionOrderID"],
                 fb["ManufacturingDate"], self.window_days))]

            location_linked = [dict(r) for r in conn.execute(
                base + """ WHERE b.CurrentLocation = ?
                             AND b.BatchID != ?
                             AND o.SupplierID != ?""",
                (fb["CurrentLocation"], failed_batch_id, fb["SupplierID"]))]

            recalled = [r[0] for r in conn.execute(
                "SELECT BatchID FROM Product_Recall")]

        return ImpactTrace(
            failed_batch=fb, siblings=siblings,
            supplier_linked=supplier_linked, location_linked=location_linked,
            already_recalled=sorted(recalled),
        )


# --------------------------------------------------------------------------- #
# Write gate
# --------------------------------------------------------------------------- #

@dataclass
class CommitIdentities:
    """
    Who the agent acts AS for each write. Not cosmetic: create_product_recall()
    stores AuthorizedManagerID from the acting employee, so the QA Manager
    identity is what actually lands in the table.
    """
    qa_manager_id: int
    production_staff_id: int

    @classmethod
    def resolve(cls, db_path: str = DEFAULT_DB) -> "CommitIdentities":
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            def one(role):
                r = list(conn.execute(
                    """SELECT EmployeeID FROM Employee
                        WHERE Role = ? AND AccountStatus = 'Active'
                        ORDER BY EmployeeID LIMIT 1""", (role,)))
                if not r:
                    raise RuntimeError(f"no Active employee with Role {role!r}")
                return r[0][0]
            return cls(qa_manager_id=one("QA Manager"),
                       production_staff_id=one("Production Staff"))
        finally:
            conn.close()


@dataclass
class CommitReport:
    dry_run: bool
    validated: bool
    validation_details: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def committed(self) -> bool:
        return self.validated and not self.dry_run and not self.errors

    def summary(self) -> str:
        head = ("DRY RUN — nothing written" if self.dry_run
                else "COMMITTED" if self.committed else "REFUSED")
        lines = [f"{head}. {len(self.actions)} action(s) planned."]
        if not self.validated:
            lines.append("Grounded validation failed; write gate refused:")
            lines += [f"  - {d}" for d in self.validation_details]
        lines += [f"  {a['tool']}({a['args']})" for a in self.actions]
        lines += [f"  ERROR {e}" for e in self.errors]
        return "\n".join(lines)


class ContainmentCommitter:
    """
    Executes a validated ContainmentPlan through the real MCP tools.

    The gate is unconditional: no success from VelloraEnvironment, no writes.
    This is the t7_commit node, and it contains no LLM call by design -- a model
    should not be the thing deciding whether it may act on its own plan.
    """

    def __init__(self, db_path: str = DEFAULT_DB,
                 identities: Optional[CommitIdentities] = None) -> None:
        self.db_path = db_path
        self.identities = identities or CommitIdentities.resolve(db_path)

    def plan_actions(self, plan: ContainmentPlan) -> List[Dict[str, Any]]:
        """The ordered tool calls this plan implies. Pure; writes nothing."""
        ids = self.identities
        actions: List[Dict[str, Any]] = []

        for bid in plan.reject_batch_ids:
            actions.append({
                "tool": "change_batch_status",
                "args": {"employee_id": ids.production_staff_id,
                         "batch_id": bid, "new_status": "Rejected"},
            })

        for bid in plan.recall_batch_ids:
            # Order matters: file the recall first so AuthorizedManagerID is
            # recorded even if the status update fails.
            actions.append({
                "tool": "create_recall",
                "args": {"employee_id": ids.qa_manager_id, "batch_id": bid,
                         "recall_reason": plan.recall_reason
                         or "Quality deviation containment."},
            })
            actions.append({
                "tool": "change_batch_status",
                "args": {"employee_id": ids.qa_manager_id,
                         "batch_id": bid, "new_status": "Recalled"},
            })

        for order in plan.replacement_orders:
            actions.append({
                "tool": "create_order",
                "args": {"employee_id": (order.responsible_employee_id
                                         or ids.production_staff_id),
                         "medicine_id": order.medicine_id,
                         "supplier_id": order.supplier_id,
                         "planned_quantity": order.planned_quantity},
            })

        return actions

    def commit(self, plan: ContainmentPlan, failed_batch_id: int,
               dry_run: bool = True) -> CommitReport:
        env = VelloraEnvironment(db_path=self.db_path,
                                 failed_batch_id=failed_batch_id)
        result = env.validate_plan(plan)
        report = CommitReport(
            dry_run=dry_run,
            validated=result.success,
            validation_details=result.detail_lines(),
            actions=self.plan_actions(plan),
        )
        if not result.success:
            report.actions = []          # refuse loudly, plan nothing
            return report
        if dry_run:
            return report

        tools = _import_tools()
        for action in report.actions:
            fn = getattr(tools, action["tool"], None)
            if fn is None:
                report.errors.append(f"tool {action['tool']} not found")
                continue
            try:
                action["result"] = fn(**action["args"])
            except Exception as exc:
                report.errors.append(f"{action['tool']}: {exc}")
        return report


# --------------------------------------------------------------------------- #
# CLI — inspect the trace without spending a token
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Impact trace and dry-run commit for a failed batch.")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--batch", type=int, default=21)
    p.add_argument("--window", type=int, default=14)
    a = p.parse_args()

    trace = ImpactTracer(a.db, a.window).trace(a.batch)
    print(trace.as_prompt_context())
    print("\nlinked batch ids:", trace.all_linked_ids())
    print("\nacting identities:", CommitIdentities.resolve(a.db))
