"""
planning_eval/run_matrix.py — the evaluation harness.

Runs every required method against the frozen suite and emits the three
comparison tables the brief asks for.

    python -m planning_eval.run_matrix --plan            # cost estimate, no calls
    python -m planning_eval.run_matrix --table A         # decomposition
    python -m planning_eval.run_matrix --table B         # planners
    python -m planning_eval.run_matrix --table C         # self-correction
    python -m planning_eval.run_matrix --all
    python -m planning_eval.run_matrix --report          # tables from saved rows

STRATIFIED, AND SAID SO
-----------------------
Running every method against all 25 cases is thousands of calls and would not
finish on a free tier. Instead each method runs against the cases DESIGNED to
discriminate it -- which is what the tags in test_suite.py are for. Every row
records which cases it covered, so the table is complete for what it claims
rather than sparse without admitting it.

Results append to planning_eval/results/rows.jsonl and every run also drops a
full trace in artifacts/. Re-running skips rows already present unless --force,
so an interrupted evaluation resumes instead of restarting.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from planning import toolkit_bridge as tk
from planning.critique import (
    build_plan_task,
    check_notice_rubric,
    run_reflexion,
    run_self_refine,
)
from planning.domain import PLAN_OUTPUT_CONTRACT
from planning.mcp_executor import ImpactTracer
from planning.orchestrator import DeviationOrchestrator
from planning.routing import Planner
from planning.vellora_env import UngroundedBaselineEnvironment, VelloraEnvironment
from planning_eval.test_suite import SUITE, by_tag

RESULTS = Path("planning_eval/results")
ROWS = RESULTS / "rows.jsonl"

#: Mistral list prices, USD per 1k tokens. Update if you switch provider, and
#: state the figure you used in the README -- a cost column with an unstated
#: price is not reproducible.
PRICE = {
    "mistral-large-latest": (0.002, 0.006),
    "mistral-small-latest": (0.0002, 0.0006),
}


def price_for(model: str) -> tuple[float, float]:
    return PRICE.get(model, (0.0, 0.0))


# --------------------------------------------------------------------------- #
# Row model
# --------------------------------------------------------------------------- #

@dataclass
class Row:
    table: str
    case_id: str
    tag: str
    dimension: str          # what varies: the method under test
    method: str
    success: bool
    score: float
    llm_calls: int
    total_tokens: int
    latency_seconds: float
    cost_usd: float
    model: str
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def key(self) -> str:
        return f"{self.table}|{self.case_id}|{self.dimension}|{self.method}"


def load_rows() -> List[Row]:
    if not ROWS.exists():
        return []
    out = []
    for line in ROWS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(Row(**json.loads(line)))
    return out


def append_row(row: Row) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    row.timestamp = datetime.now(timezone.utc).isoformat()
    with ROWS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(row)) + "\n")


def usage_to_row_fields(usage: tk.Usage, model: str) -> Dict[str, Any]:
    pin, pout = price_for(model)
    return {
        "llm_calls": usage.calls,
        "total_tokens": usage.total_tokens,
        "latency_seconds": round(usage.seconds, 2),
        "cost_usd": round(usage.cost(pin, pout), 5),
        "model": model,
    }


# --------------------------------------------------------------------------- #
# TABLE A — decomposition-first vs dynamic
# --------------------------------------------------------------------------- #

def run_table_a(db: str, batch: int, force: bool = False,
                limit: Optional[int] = None) -> None:
    cases = by_tag("DEC-DYNAMIC") + by_tag("DEC-STATIC")
    if limit:
        cases = cases[:limit]
    done = {r.key() for r in load_rows()}

    for case in cases:
        for mode in ("static", "dynamic"):
            row_key = f"A|{case.id}|decomposition|{mode}"
            if row_key in done and not force:
                print(f"  skip {row_key}")
                continue
            fb = case.env_kwargs.get("failed_batch_id", batch)
            orch = DeviationOrchestrator(db_path=db, failed_batch_id=fb)
            print(f"  running {case.id} [{mode}] ...")
            res = orch.run(case.prompt, mode=mode, case_id=case.id)
            res.save()

            plan_node = next((n for n in res.nodes
                              if n.grounded_success is not None), None)
            u = res.total_usage or {}
            pin, pout = price_for(tk.DEFAULT_MODEL)
            append_row(Row(
                table="A", case_id=case.id, tag=case.tag,
                dimension="decomposition", method=mode,
                success=bool(plan_node and plan_node.grounded_success),
                score=float(plan_node.grounded_score) if plan_node else 0.0,
                llm_calls=u.get("llm_calls", 0),
                total_tokens=u.get("total_tokens", 0),
                latency_seconds=u.get("latency_seconds", 0.0),
                cost_usd=round((u.get("prompt_tokens", 0) / 1000 * pin
                                + u.get("completion_tokens", 0) / 1000 * pout), 5),
                model=tk.DEFAULT_MODEL,
                detail={"nodes": len(res.nodes),
                        "batches": res.execution_batches,
                        "dynamic_steps": len(res.dynamic_steps),
                        "error": res.error},
            ))


# --------------------------------------------------------------------------- #
# TABLE B — Plan-and-Solve vs Tree of Thoughts vs LATS
# --------------------------------------------------------------------------- #

B_METHODS = [
    ("plan_and_solve", Planner.PLAN_AND_SOLVE, True),
    ("tree_of_thoughts", Planner.TREE_OF_THOUGHTS, True),
    ("lats_grounded", Planner.LATS, True),
    ("lats_ungrounded", Planner.LATS, False),   # the required control row
]


def _score_plan(text: str, db: str, batch: int) -> tuple[bool, float, List[Dict]]:
    env = VelloraEnvironment(db_path=db, failed_batch_id=batch)
    fb = env.evaluate(text)
    checks = env.last_result.as_trace() if env.last_result else []
    return fb.success, fb.score, checks


def run_table_b(db: str, batch: int, force: bool = False,
                limit: Optional[int] = None) -> None:
    """
    Sub-task level, not full-DAG: isolating t5_plan is what makes the planner
    comparison a comparison of PLANNERS rather than of everything upstream.
    """
    cases = [c for c in SUITE if c.target_subtask == "t5_plan"]
    if limit:
        cases = cases[:limit]
    done = {r.key() for r in load_rows()}

    for case in cases:
        fb_batch = case.env_kwargs.get("failed_batch_id", batch)
        task = build_plan_task(db, fb_batch)

        for name, planner, grounded in B_METHODS:
            row_key = f"B|{case.id}|planner|{name}"
            if row_key in done and not force:
                print(f"  skip {row_key}")
                continue
            print(f"  running {case.id} [{name}] ...")
            t0 = time.perf_counter()
            output, err = "", ""
            with tk.metered() as (llm, usage):
                try:
                    if planner is Planner.PLAN_AND_SOLVE:
                        output = tk.plan_and_solve(task, llm)
                    elif planner is Planner.TREE_OF_THOUGHTS:
                        thoughts = tk.tree_of_thoughts(task, llm, depth=2,
                                                       beam_width=2)
                        best = max(thoughts, key=lambda t: t.score, default=None)
                        output = best.state if best else ""
                    else:
                        env = (VelloraEnvironment(db_path=db,
                                                  failed_batch_id=fb_batch)
                               if grounded else UngroundedBaselineEnvironment())
                        from planning.orchestrator import _lats_output
                        output = _lats_output(
                            tk.lats(task, llm, env, iterations=2, n_actions=2))
                except Exception as exc:
                    err = f"{type(exc).__name__}: {exc}"

            # EVERY row is scored by the GROUNDED environment, including the
            # ungrounded-LATS row. The ungrounded variant differs in what
            # guided its SEARCH, not in how we judge its ANSWER -- otherwise
            # the two rows would not be comparable.
            ok, score, checks = _score_plan(output, db, fb_batch)
            append_row(Row(
                table="B", case_id=case.id, tag=case.tag,
                dimension="planner", method=name,
                success=ok, score=score,
                **usage_to_row_fields(usage, tk.DEFAULT_MODEL),
                detail={"error": err,
                        "failed_checks": [c["name"] for c in checks
                                          if not c["passed"] and not c["skipped"]],
                        "wall": round(time.perf_counter() - t0, 2)},
            ))


# --------------------------------------------------------------------------- #
# TABLE C — Self-Refine vs Reflexion (and the buffer ablation)
# --------------------------------------------------------------------------- #

C_METHODS = ["self_refine", "reflexion_mem2", "reflexion_mem0"]


def run_table_c(db: str, batch: int, force: bool = False,
                limit: Optional[int] = None) -> None:
    cases = by_tag("RFX") + by_tag("SRF")
    if limit:
        cases = cases[:limit]
    done = {r.key() for r in load_rows()}

    for case in cases:
        fb_batch = case.env_kwargs.get("failed_batch_id", batch)
        is_prose = case.target_subtask == "t6_notice"

        for method in C_METHODS:
            row_key = f"C|{case.id}|self_correction|{method}"
            if row_key in done and not force:
                print(f"  skip {row_key}")
                continue
            print(f"  running {case.id} [{method}] ...")
            success, score, detail = False, 0.0, {}

            with tk.metered() as (llm, usage):
                try:
                    if method == "self_refine":
                        if is_prose:
                            ctx = ImpactTracer(db, 14).trace(fb_batch)
                            goal = (f"{case.prompt}\n\nDATABASE FACTS:\n"
                                    + ctx.as_prompt_context())
                            draft = tk.plan_and_solve(goal, llm)
                            res = run_self_refine(goal, draft, llm, usage,
                                                  max_chars=500)
                            after = res.rubric_after
                            success = bool(after and after.passed)
                            score = (len(after.present) /
                                     max(len(after.present) + len(after.missing), 1)
                                     ) if after else 0.0
                            detail = {"missing_before": res.rubric_before.missing,
                                      "missing_after": after.missing if after else [],
                                      "improved": res.improved}
                        else:
                            task = build_plan_task(db, fb_batch)
                            draft = tk.plan_and_solve(task, llm)
                            res = run_self_refine(task, draft, llm, usage)
                            success, score, checks = _score_plan(
                                res.revised, db, fb_batch)
                            detail = {"failed_checks": [
                                c["name"] for c in checks
                                if not c["passed"] and not c["skipped"]]}
                    else:
                        mem = 2 if method == "reflexion_mem2" else 0
                        env = VelloraEnvironment(db_path=db,
                                                 failed_batch_id=fb_batch)
                        task = build_plan_task(db, fb_batch)
                        run = run_reflexion(task, llm, env, max_trials=3,
                                            memory_size=mem)
                        success = run.success
                        score = max((t["score"] for t in run.trials), default=0.0)
                        detail = {"trials_used": run.trials_used,
                                  "memory_size": mem,
                                  "per_trial": [
                                      {"trial": t["trial"], "score": t["score"],
                                       "failed": t["failed_checks"][:2]}
                                      for t in run.trials],
                                  "reflections": run.memory}
                except Exception as exc:
                    detail = {"error": f"{type(exc).__name__}: {exc}"}

            append_row(Row(
                table="C", case_id=case.id, tag=case.tag,
                dimension="self_correction", method=method,
                success=success, score=round(score, 4),
                **usage_to_row_fields(usage, tk.DEFAULT_MODEL),
                detail=detail,
            ))


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def errored(row: Row) -> bool:
    """A row whose run aborted on a provider error. These MUST be excluded from
    method comparisons: a 503 storm is not evidence about decomposition."""
    return bool(row.detail.get("error"))


def _agg(rows: List[Row]) -> Dict[str, Any]:
    bad = [r for r in rows if errored(r)]
    good = [r for r in rows if not errored(r)]
    n = len(good)
    if not n:
        return {"n": 0, "errors": len(bad), "success": f"0/0 ({len(bad)} errored)",
                "mean_score": 0, "calls": 0, "tokens": 0, "latency": 0, "cost": 0}
    return {
        "n": n,
        "errors": len(bad),
        "success": f"{sum(1 for r in good if r.success)}/{n}"
                   + (f"  ({len(bad)} errored, excluded)" if bad else ""),
        "mean_score": round(statistics.mean(r.score for r in good), 3),
        "calls": round(statistics.mean(r.llm_calls for r in good), 1),
        "tokens": int(statistics.mean(r.total_tokens for r in good)),
        "latency": round(statistics.mean(r.latency_seconds for r in good), 1),
        "cost": round(statistics.mean(r.cost_usd for r in good), 5),
    }


TABLE_TITLES = {
    "A": "Table A — Top-level decomposition (same request type, both methods)",
    "B": "Table B — Planning algorithms on the t5_plan sub-task",
    "C": "Table C — Self-correction",
}


def report() -> str:
    rows = load_rows()
    if not rows:
        return "No results yet. Run --table A/B/C first."
    out: List[str] = []
    for table in ("A", "B", "C"):
        subset = [r for r in rows if r.table == table]
        if not subset:
            continue
        out.append(f"\n### {TABLE_TITLES[table]}\n")
        out.append("| Method | Task success | Mean grounded score | Avg LLM calls "
                   "| Avg tokens | Avg latency (s) | Est. cost/run |")
        out.append("|---|---|---|---|---|---|---|")
        methods = sorted({r.method for r in subset})
        for m in methods:
            a = _agg([r for r in subset if r.method == m])
            out.append(f"| {m} | {a['success']} | {a['mean_score']} | "
                       f"{a['calls']} | {a['tokens']} | {a['latency']} | "
                       f"${a['cost']} |")
        cases = sorted({r.case_id for r in subset})
        out.append(f"\nCases covered ({len(cases)}): {', '.join(cases)}")
        models = sorted({r.model for r in subset})
        out.append(f"Model(s): {', '.join(models)}")
        bad = [r for r in subset if errored(r)]
        if bad:
            out.append(f"\n**{len(bad)} run(s) aborted on provider errors and "
                       f"are excluded from the averages above.** Re-run with "
                       f"`--retry-errors` before citing this table:")
            for r in sorted(bad, key=lambda x: (x.case_id, x.method)):
                out.append(f"  - {r.case_id} [{r.method}]: "
                           f"{str(r.detail.get('error'))[:90]}")
        out.append("")

    # The contrast the guardrails single out.
    b = [r for r in rows if r.table == "B"]
    if b:
        g = _agg([r for r in b if r.method == "lats_grounded"])
        u = _agg([r for r in b if r.method == "lats_ungrounded"])
        if g["n"] and u["n"]:
            out.append("\n### Grounded vs ungrounded LATS\n")
            out.append(f"Grounded  : {g['success']} success, mean score "
                       f"{g['mean_score']}, {g['calls']} calls")
            out.append(f"Ungrounded: {u['success']} success, mean score "
                       f"{u['mean_score']}, {u['calls']} calls")
            out.append("\nBoth rows are scored by the SAME grounded environment; "
                       "only the signal guiding the search differs.")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Planning / cost estimate
# --------------------------------------------------------------------------- #

def plan_only() -> str:
    a = len(by_tag("DEC-DYNAMIC") + by_tag("DEC-STATIC")) * 2
    b = len([c for c in SUITE if c.target_subtask == "t5_plan"]) * len(B_METHODS)
    c = len(by_tag("RFX") + by_tag("SRF")) * len(C_METHODS)
    est_calls = a * 14 + b * 6 + c * 5
    return (f"Table A: {a} runs (8 cases x 2 modes)\n"
            f"Table B: {b} runs ({b // len(B_METHODS)} cases x "
            f"{len(B_METHODS)} methods)\n"
            f"Table C: {c} runs ({c // len(C_METHODS)} cases x "
            f"{len(C_METHODS)} methods)\n"
            f"TOTAL   : {a + b + c} runs, roughly {est_calls} LLM calls\n\n"
            f"At the current throttle that is several hours. Run one table at a "
            f"time; rows.jsonl makes it resumable.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    p = argparse.ArgumentParser()
    p.add_argument("--table", choices=["A", "B", "C"])
    p.add_argument("--all", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--db", default="db/vellora.db")
    p.add_argument("--batch", type=int, default=21)
    p.add_argument("--limit", type=int, default=None,
                   help="cap cases per table, for a cheap trial run")
    p.add_argument("--force", action="store_true", help="re-run existing rows")
    p.add_argument("--retry-errors", action="store_true",
                   help="delete rows that aborted on provider errors so they "
                        "are re-run; keeps good rows intact")
    a = p.parse_args()

    if a.retry_errors:
        rows = load_rows()
        keep = [r for r in rows if not errored(r)]
        dropped = len(rows) - len(keep)
        RESULTS.mkdir(parents=True, exist_ok=True)
        with ROWS.open("w", encoding="utf-8") as fh:
            for r in keep:
                fh.write(json.dumps(asdict(r)) + "\n")
        print(f"dropped {dropped} errored row(s); re-run the table(s) to fill them")

    if a.plan:
        print(plan_only())
    elif a.report:
        print(report())
    else:
        tables = ["A", "B", "C"] if a.all else ([a.table] if a.table else [])
        if not tables:
            p.print_help()
        for t in tables:
            print(f"\n=== TABLE {t} ===")
            {"A": run_table_a, "B": run_table_b, "C": run_table_c}[t](
                a.db, a.batch, force=a.force, limit=a.limit)
        print(report())
        out = RESULTS / "tables.md"
        out.write_text(report(), encoding="utf-8")
        print(f"\nwritten to {out}")
