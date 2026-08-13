"""
planning/toolkit_bridge.py — the ONLY file that touches toolkit internals.

VERIFIED against the real fork API (introspected 2026-08-13). No guesses left.

Design rule for this whole folder:
    The toolkit owns the SEARCH. We own the DOMAIN.
    Nothing here re-implements a search loop, a scheduler, a beam, a UCT
    formula, or a topological sort. If you find yourself writing one, stop --
    that is the 50% penalty clause.

Real toolkit API
----------------
decomposition.decompose_goal(goal, llm) -> Plan
decomposition.execute_plan(plan, llm, max_workers=4) -> dict[str, str]
decomposition.final_output(plan, outputs) -> str
dynamic_decomposition.dynamic_decomposition(goal, llm, max_steps=4)
        -> list[tuple[str, str]]        # (instruction, observation) pairs
plan_and_solve.plan_and_solve(question, llm) -> str
tree_of_thoughts.tree_of_thoughts(problem, llm, depth=2, beam_width=2)
        -> list[Thought]
lats.lats(task, llm, environment, iterations=2, n_actions=2,
          exploration_weight=1.414) -> LATSResult
lats.flatten_lats_tree(root) -> list[dict]
self_refine.reflect_and_refine(goal, draft, llm) -> ReflectionResult
self_refine.deterministic_checks(goal, draft) -> list[str]
reflexion.reflexion(task, llm, environment, max_trials=3, memory_size=3)
        -> ReflexionResult

Note what is NOT there: decompose_goal and dynamic_decomposition take no
`environment`. Grounding for the decomposition modes therefore happens in OUR
node executor, not inside the toolkit's planners.
"""

from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent / "toolkit"))

import argparse
import importlib
import inspect
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

TOOLKIT_ROOT = "planning_lab.algorithms"

MODULES = {
    "decomposition": f"{TOOLKIT_ROOT}.decomposition",
    "dynamic_decomposition": f"{TOOLKIT_ROOT}.dynamic_decomposition",
    "plan_and_solve": f"{TOOLKIT_ROOT}.plan_and_solve",
    "tree_of_thoughts": f"{TOOLKIT_ROOT}.tree_of_thoughts",
    "lats": f"{TOOLKIT_ROOT}.lats",
    "self_refine": f"{TOOLKIT_ROOT}.self_refine",
    "reflexion": f"{TOOLKIT_ROOT}.reflexion",
    "environment": f"{TOOLKIT_ROOT}.environment",
}


def load(name: str):
    return importlib.import_module(MODULES[name])


# Re-export the toolkit's own models so nothing downstream redefines them.
from planning_lab.models import (  # noqa: E402
    EnvironmentFeedback,
    Plan,
    Task,
    Thought,
)

__all__ = [
    "EnvironmentFeedback", "Plan", "Task", "Thought",
    "build_model", "build_independent_critic", "metered", "Usage",
    "decompose_goal", "execute_plan", "final_output",
    "dynamic_decomposition", "plan_and_solve", "tree_of_thoughts",
    "lats", "flatten_lats_tree", "reflect_and_refine",
    "deterministic_checks", "reflexion",
]


# --------------------------------------------------------------------------- #
# 1. Model provider
# --------------------------------------------------------------------------- #
# The toolkit calls llm.with_structured_output(schema, method="json_schema").
# Keep that INTERFACE; only change which client provides it.
#
# ADAPT: if the team is already on OpenAI/Gemini elsewhere in the repo, swap the
# constructor here so the whole repo has one provider, one key in .env, and one
# cost-per-token constant in the comparison table.

def build_model(model_name: Optional[str] = None, temperature: float = 0.2):
    # --- ADAPT START ---
    from langchain_mistralai import ChatMistralAI
    return ChatMistralAI(
        model=model_name or "mistral-large-latest",
        temperature=temperature,
    )
    # --- ADAPT END ---


def build_independent_critic():
    """
    A DIFFERENT model from build_model(), for the independent-critic ablation
    the brief asks for. Used in planning/critique.py.
    """
    # --- ADAPT START ---
    return build_model(model_name="mistral-small-latest", temperature=0.0)
    # --- ADAPT END ---


# --------------------------------------------------------------------------- #
# 2. Call / token / latency accounting
# --------------------------------------------------------------------------- #
# The comparison table needs calls, tokens, latency and cost per run. Wrap the
# model once instead of instrumenting seven algorithm files: every algorithm
# receives this object, so every call is counted whichever search loop makes it.

@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost(self, per_1k_in: float, per_1k_out: float) -> float:
        return (self.prompt_tokens / 1000 * per_1k_in
                + self.completion_tokens / 1000 * per_1k_out)

    def as_trace(self) -> Dict[str, Any]:
        return {
            "llm_calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_seconds": round(self.seconds, 3),
        }


class MeteredModel:
    """
    Counting proxy around a LangChain chat model.

    Forwards unknown attributes to the wrapped client, so it survives duck
    typing. If a toolkit function ever does a hard
    `isinstance(llm, BaseChatModel)` check, pass the raw model instead and read
    call counts off the artifacts/ trace.
    """

    def __init__(self, inner: Any, usage: Usage) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_usage", usage)

    def _meter(self, fn, *a, **kw):
        u: Usage = object.__getattribute__(self, "_usage")
        t0 = time.perf_counter()
        out = fn(*a, **kw)
        u.seconds += time.perf_counter() - t0
        u.calls += 1
        meta = getattr(out, "usage_metadata", None)
        if not meta:
            rm = getattr(out, "response_metadata", {}) or {}
            meta = rm.get("token_usage", {}) if isinstance(rm, dict) else {}
        if isinstance(meta, dict):
            u.prompt_tokens += int(meta.get("input_tokens")
                                   or meta.get("prompt_tokens") or 0)
            u.completion_tokens += int(meta.get("output_tokens")
                                       or meta.get("completion_tokens") or 0)
        return out

    def invoke(self, *a, **kw):
        return self._meter(object.__getattribute__(self, "_inner").invoke, *a, **kw)

    def with_structured_output(self, *a, **kw):
        inner = object.__getattribute__(self, "_inner")
        return MeteredModel(inner.with_structured_output(*a, **kw),
                            object.__getattribute__(self, "_usage"))

    def __getattr__(self, item):
        return getattr(object.__getattribute__(self, "_inner"), item)


@contextmanager
def metered(model_name: Optional[str] = None, temperature: float = 0.2):
    """
    Usage:
        with metered() as (llm, usage):
            answer = plan_and_solve("...", llm)
        print(usage.as_trace())
    """
    usage = Usage()
    yield MeteredModel(build_model(model_name, temperature), usage), usage


# --------------------------------------------------------------------------- #
# 3. Entry points — direct pass-throughs to the verified signatures
# --------------------------------------------------------------------------- #

def decompose_goal(goal: str, llm) -> "Plan":
    """Decomposition-first: whole plan up front. Returns a validated Plan;
    models.Plan.validate_dag already rejects cycles at construction time."""
    return load("decomposition").decompose_goal(goal, llm)


def execute_plan(plan: "Plan", llm, max_workers: int = 4) -> Dict[str, str]:
    """Runs the plan in dependency-safe parallel batches. Batch structure comes
    from plan.execution_batches() -- do not re-schedule it yourself."""
    return load("decomposition").execute_plan(plan, llm, max_workers=max_workers)


def final_output(plan: "Plan", outputs: Dict[str, str]) -> str:
    return load("decomposition").final_output(plan, outputs)


def dynamic_decomposition(goal: str, llm, max_steps: int = 4) -> List[Tuple[str, str]]:
    """Interleaved: next sub-task chosen after observing the last result.
    Returns (instruction, observation) pairs in execution order."""
    return load("dynamic_decomposition").dynamic_decomposition(
        goal, llm, max_steps=max_steps)


def plan_and_solve(question: str, llm) -> str:
    return load("plan_and_solve").plan_and_solve(question, llm)


def tree_of_thoughts(problem: str, llm, depth: int = 2,
                     beam_width: int = 2) -> List["Thought"]:
    return load("tree_of_thoughts").tree_of_thoughts(
        problem, llm, depth=depth, beam_width=beam_width)


def lats(task: str, llm, environment, iterations: int = 2, n_actions: int = 2,
         exploration_weight: float = 1.414):
    """
    `environment` MUST be a VelloraEnvironment for any run reported as grounded.
    Passing the toolkit's randomized default here and calling it grounded is the
    exact failure the guardrails describe.
    """
    return load("lats").lats(task, llm, environment, iterations=iterations,
                             n_actions=n_actions,
                             exploration_weight=exploration_weight)


def flatten_lats_tree(root) -> List[dict]:
    """Node-by-node MCTS record: visits, environment_score, model_score,
    feedback. Evidence for the ToT-self-score vs LATS-env-score comparison."""
    return load("lats").flatten_lats_tree(root)


def reflect_and_refine(goal: str, draft: str, llm):
    """Self-Refine: one draft in, critique + revision out."""
    return load("self_refine").reflect_and_refine(goal, draft, llm)


def deterministic_checks(goal: str, draft: str) -> List[str]:
    """The toolkit's own non-LLM checks. Our grounded rubric checks in
    planning/critique.py extend these rather than replacing them."""
    return load("self_refine").deterministic_checks(goal, draft)


def reflexion(task: str, llm, environment, max_trials: int = 3,
              memory_size: int = 3):
    """memory_size=0 is the ablation proving the episodic buffer does work."""
    return load("reflexion").reflexion(task, llm, environment,
                                       max_trials=max_trials,
                                       memory_size=memory_size)


# --------------------------------------------------------------------------- #
# Introspection
# --------------------------------------------------------------------------- #

def introspect() -> None:
    print("Toolkit API as actually present in your fork:\n")
    for path in MODULES.values():
        try:
            m = importlib.import_module(path)
        except Exception as exc:
            print(f"  {path}\n    IMPORT FAILED: {exc}\n")
            continue
        print(f"  {path}")
        for n, o in sorted(vars(m).items()):
            if n.startswith("_") or getattr(o, "__module__", None) != path:
                continue
            if inspect.isclass(o):
                meths = [x for x in vars(o) if not x.startswith("_")]
                print(f"    class {n}({', '.join(b.__name__ for b in o.__bases__)})"
                      f"  methods: {meths}")
            elif callable(o):
                try:
                    print(f"    def {n}{inspect.signature(o)}")
                except (ValueError, TypeError):
                    print(f"    def {n}(...)")
        print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--introspect", action="store_true")
    if p.parse_args().introspect:
        introspect()
    else:
        p.print_help()
