"""
planning/critique.py — the self-correction concern, both scopes.

GRADER: Self-Refine and Reflexion live here, along with the statement of what
each critique's source of truth is.

    Self-Refine   one draft, one critique against an explicit rubric, one
                  revision. Scoped to t6_notice, where output is prose, cheap
                  to regenerate, and checkable field by field.

    Reflexion     the whole t5_plan sub-task retried across trials, carrying a
                  capped buffer of verbal reflections. Scoped here because the
                  failure modes STACK: fixing the supplier does not fix the
                  authorizer, and a single retry only ever fixes the first
                  thing that broke.

SOURCE OF TRUTH, PER CRITIQUE STEP
----------------------------------
    Self-Refine, deterministic layer  toolkit deterministic_checks() + our
                                      NoticeRubric field checks (grounded:
                                      string/structure assertions, no model)
    Self-Refine, LLM layer            model critique against the rubric
                                      (ungrounded, and labelled as such)
    Reflexion, evaluate step          VelloraEnvironment, 8 SQL checks
                                      (grounded)
    Reflexion, reflection text        model, but conditioned ONLY on the named
                                      failed checks, so reflections cite
                                      constraints rather than vibes

The independent-critic ablation the brief asks for is run_self_refine(...,
independent_critic=True), which swaps in a different model for the critique
step while holding the drafter fixed.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import toolkit_bridge as tk
from .domain import PLAN_OUTPUT_CONTRACT
from .mcp_executor import ImpactTracer
from .vellora_env import (
    UngroundedBaselineEnvironment,
    VelloraEnvironment,
    parse_candidate,
)

DEFAULT_DB = "db/vellora.db"


# --------------------------------------------------------------------------- #
# Self-Refine: the rubric
# --------------------------------------------------------------------------- #

@dataclass
class RubricField:
    name: str
    description: str
    #: Regex that must match the draft for this field to count as present.
    pattern: str
    required: bool = True


#: The QA notice rubric. Every entry is checkable WITHOUT a model, which is what
#: makes this critique layer grounded: we are asserting facts about the string,
#: not asking an LLM whether it liked its own writing.
NOTICE_RUBRIC: List[RubricField] = [
    RubricField("failed_batch", "names the failed batch id",
                r"\bbatch\s*#?\s*\d+", True),
    RubricField("failed_test", "names the test that failed",
                r"steril|assay|stabilit|quality\s+test", True),
    RubricField("scope_reasoning", "explains why batches were included",
                r"because|due to|linked|shares?|traced", True),
    RubricField("exclusion_reasoning", "explains what was NOT contained and why",
                r"not\s+(?:contained|recalled|affected|included)|excluded|"
                r"different\s+supplier|no\s+linkage", True),
    RubricField("owner", "assigns an owner to containment actions",
                r"authoriz|approv|responsible|owner|QA\s+Manager", True),
    RubricField("hypothesis_marked", "marks root cause as provisional",
                r"suspect|likely|probable|hypothes|pending|under\s+investigation|"
                r"provisional|preliminary", True),
    RubricField("replacement", "states the replacement production plan",
                r"replacement|re-?order|new\s+production|production\s+order", True),
]


@dataclass
class RubricResult:
    missing: List[str] = field(default_factory=list)
    present: List[str] = field(default_factory=list)
    over_length: bool = False

    @property
    def passed(self) -> bool:
        return not self.missing and not self.over_length

    def as_issues(self) -> List[str]:
        issues = [f"missing rubric field '{n}'" for n in self.missing]
        if self.over_length:
            issues.append("exceeds the 500-character Product_Recall.RecallReason "
                          "column limit")
        return issues


def check_notice_rubric(draft: str, max_chars: Optional[int] = None
                        ) -> RubricResult:
    """
    Grounded field check. No model involved.

    max_chars enforces the real schema limit: Product_Recall.RecallReason is
    VARCHAR(500), so a beautifully written notice that will not fit the column
    is a failed notice.
    """
    res = RubricResult()
    low = draft.lower()
    for f in NOTICE_RUBRIC:
        if re.search(f.pattern, low, re.IGNORECASE):
            res.present.append(f.name)
        elif f.required:
            res.missing.append(f.name)
    if max_chars is not None and len(draft) > max_chars:
        res.over_length = True
    return res


# --------------------------------------------------------------------------- #
# Self-Refine
# --------------------------------------------------------------------------- #

@dataclass
class RefineResult:
    draft: str
    critique: str
    revised: str
    #: Issues from the toolkit's own deterministic_checks().
    toolkit_issues: List[str] = field(default_factory=list)
    rubric_before: Optional[RubricResult] = None
    rubric_after: Optional[RubricResult] = None
    critic_model: str = "same as drafter"
    usage: Dict[str, Any] = field(default_factory=dict)

    @property
    def improved(self) -> bool:
        if not (self.rubric_before and self.rubric_after):
            return False
        return len(self.rubric_after.missing) < len(self.rubric_before.missing)

    def as_trace(self) -> Dict[str, Any]:
        return {
            "method": "self_refine",
            "critic_model": self.critic_model,
            "toolkit_issues": self.toolkit_issues,
            "rubric_missing_before": (self.rubric_before.missing
                                      if self.rubric_before else []),
            "rubric_missing_after": (self.rubric_after.missing
                                     if self.rubric_after else []),
            "improved": self.improved,
            "critique": self.critique,
            "draft": self.draft,
            "revised": self.revised,
            "usage": self.usage,
        }


def run_self_refine(goal: str, draft: str, llm, usage: tk.Usage,
                    max_chars: Optional[int] = None,
                    independent_critic: bool = False) -> RefineResult:
    """
    One draft, one critique, one revision — the toolkit's reflect_and_refine,
    with our grounded rubric folded into the goal so the critic is told what
    concretely is missing rather than asked for an opinion.

    independent_critic=True runs the critique with a DIFFERENT model, which is
    the ablation the brief asks for. Note the toolkit's reflect_and_refine takes
    a single llm, so the swap is done by passing the critic model as `llm` for
    the whole call and reporting it as such -- an honest description of what
    actually varied.
    """
    before = check_notice_rubric(draft, max_chars)
    toolkit_issues = tk.deterministic_checks(goal, draft)

    grounded_note = ""
    if before.as_issues():
        grounded_note = (
            "\n\nGROUNDED CHECKS ALREADY FAILED (fix these specifically):\n"
            + "\n".join(f"- {i}" for i in before.as_issues()))

    critic_llm = llm
    critic_name = "same as drafter"
    if independent_critic:
        # The callback is what counts tokens; a critic built without it reports
        # near-zero usage and makes the ablation look free.
        critic_raw = tk.build_model(tk.CRITIC_MODEL, temperature=0.0,
                                    callbacks=[tk._UsageCallback(usage)])
        critic_llm = tk.MeteredModel(critic_raw, usage)
        critic_name = tk.CRITIC_MODEL

    result = tk.reflect_and_refine(goal + grounded_note, draft, critic_llm)

    return RefineResult(
        draft=result.draft,
        critique=result.critique,
        revised=result.revised,
        toolkit_issues=list(result.grounded_issues) + toolkit_issues,
        rubric_before=before,
        rubric_after=check_notice_rubric(result.revised, max_chars),
        critic_model=critic_name,
    )


# --------------------------------------------------------------------------- #
# Reflexion
# --------------------------------------------------------------------------- #

@dataclass
class ReflexionRun:
    success: bool
    output: str
    trials: List[Dict[str, Any]] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)
    memory_size: int = 3
    grounded: bool = True
    usage: Dict[str, Any] = field(default_factory=dict)

    @property
    def trials_used(self) -> int:
        return len(self.trials)

    def as_trace(self) -> Dict[str, Any]:
        return {
            "method": "reflexion",
            "grounded": self.grounded,
            "memory_size": self.memory_size,
            "success": self.success,
            "trials_used": self.trials_used,
            "trials": self.trials,
            "episodic_memory": self.memory,
            "output": self.output,
            "usage": self.usage,
        }


def run_reflexion(task: str, llm, environment, max_trials: int = 3,
                  memory_size: int = 3) -> ReflexionRun:
    """
    Retry the whole sub-task across trials, carrying verbal reflections forward.

    memory_size=0 ablates the buffer entirely and is the control that shows the
    memory is doing work rather than the extra attempts alone. The stock toolkit
    rejects memory_size < 1; our fork permits 0 (see the commit on branch
    vellora/memory-size-ablation).
    """
    result = tk.reflexion(task, llm, environment, max_trials=max_trials,
                          memory_size=memory_size)

    trials = []
    for t in result.trials:
        trials.append({
            "trial": t.number,
            "score": t.feedback.score,
            "success": t.feedback.success,
            # The failed CHECK NAMES, which is what the reflection was
            # conditioned on. This is the grounding audit trail.
            "failed_checks": [d for d in t.feedback.details
                              if d.startswith("[")],
            "reflection": t.reflection,
            "attempt_excerpt": (t.attempt or "")[:400],
        })

    return ReflexionRun(
        success=result.success,
        output=result.output,
        trials=trials,
        memory=list(result.memory),
        memory_size=memory_size,
        grounded=isinstance(environment, VelloraEnvironment),
    )


def build_plan_task(db_path: str, failed_batch_id: int,
                    window_days: int = 14) -> str:
    """The t5_plan task string, self-contained so Reflexion can retry it whole."""
    ctx = ImpactTracer(db_path, window_days).trace(failed_batch_id)
    return (
        "You are the Vellora Deviation Response Agent.\n\n"
        f"Batch {failed_batch_id} failed its quality test. Produce the complete "
        "containment plan: which linked batches to recall, which to reject, "
        "which to merely watch, who authorizes the recalls, and what "
        "replacement production orders to raise.\n\n"
        "DATABASE FACTS (authoritative, do not contradict):\n"
        + ctx.as_prompt_context() + "\n\n"
        + PLAN_OUTPUT_CONTRACT
    )


# --------------------------------------------------------------------------- #
# CLI — run one self-correction experiment
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    p = argparse.ArgumentParser()
    p.add_argument("--method", choices=["self_refine", "reflexion"],
                   default="reflexion")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--batch", type=int, default=21)
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--memory-size", type=int, default=2,
                   help="0 ablates the episodic buffer")
    p.add_argument("--ungrounded", action="store_true")
    p.add_argument("--independent-critic", action="store_true")
    p.add_argument("--max-chars", type=int, default=None,
                   help="enforce the Product_Recall.RecallReason VARCHAR(500) "
                        "limit; pass 500 for the recall-reason variant")
    a = p.parse_args()

    with tk.metered() as (llm, usage):
        if a.method == "reflexion":
            env = (UngroundedBaselineEnvironment() if a.ungrounded
                   else VelloraEnvironment(db_path=a.db,
                                           failed_batch_id=a.batch))
            task = build_plan_task(a.db, a.batch)
            run = run_reflexion(task, llm, env, max_trials=a.trials,
                                memory_size=a.memory_size)
            run.usage = usage.as_trace()
            print(f"\ngrounded={run.grounded}  memory_size={run.memory_size}  "
                  f"success={run.success}  trials_used={run.trials_used}")
            for t in run.trials:
                print(f"\n  trial {t['trial']}: score={t['score']} "
                      f"success={t['success']}")
                for c in t["failed_checks"]:
                    print(f"    FAILED {c[:120]}")
                if t["reflection"]:
                    print(f"    reflection: {t['reflection'][:220]}")
            print("\nusage:", run.usage)
        else:
            # DELIBERATELY TERSE. This is what a QA lead actually types. A goal
            # that recites the rubric produces a first draft that already
            # satisfies it, and a critique loop with nothing to catch measures
            # nothing -- which is exactly what our first run showed.
            ctx = ImpactTracer(a.db, 14).trace(a.batch)
            goal = (f"Write the internal QA deviation notice for the batch "
                    f"{a.batch} sterility failure.\n\n"
                    f"DATABASE FACTS:\n{ctx.as_prompt_context()}")
            draft = tk.plan_and_solve(goal, llm)
            res = run_self_refine(goal, draft, llm, usage,
                                  max_chars=a.max_chars,
                                  independent_critic=a.independent_critic)
            res.usage = usage.as_trace()
            print(f"\ncritic model: {res.critic_model}")
            print("rubric missing BEFORE:", res.rubric_before.missing)
            print("rubric missing AFTER :", res.rubric_after.missing)
            print("improved:", res.improved)
            print("\nDRAFT (first 400 chars):\n", res.draft[:400])
            print("\ncritique:\n", res.critique[:700])
            print("\nREVISED (first 400 chars):\n", res.revised[:400])
            print("\nusage:", res.usage)
