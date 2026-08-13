"""
planning/toolkit_bridge.py — the ONLY file that touches toolkit internals.

Everything else in planning/ imports from here, so when your fork's signatures
differ from what's assumed below, there is exactly one file to fix.

Design rule for this whole folder:
    The toolkit owns the SEARCH. We own the DOMAIN.
    Nothing here re-implements a search loop, a scheduler, a beam, a UCT
    formula, or a topological sort. If you find yourself writing one, stop --
    that is the 50% penalty clause.

What we DO here:
  * swap the model provider (toolkit ships ChatMistralAI; use whatever your
    repo already uses so you have one provider, one key, one cost model)
  * inject VelloraEnvironment where the toolkit constructs its randomized one
  * wrap each entry point so calls/tokens/latency land in the toolkit's own
    artifacts/ trace rather than a second logging system

Run `python -m planning.toolkit_bridge --introspect` to print the real
signatures of your fork. Fix the ADAPT blocks against that output.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

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


# --------------------------------------------------------------------------- #
# 1. Model provider swap
# --------------------------------------------------------------------------- #
# The toolkit builds ChatMistralAI(...).with_structured_output(schema,
# method="json_schema"). Keep that INTERFACE -- the algorithms depend on getting
# a structured object back -- and only change which client produces it.
#
# ADAPT: point this at whatever your repo already uses (the same client your
# memory/RAG agent uses). One provider across the repo means one key in .env and
# one cost-per-token constant in the comparison table.

def build_model(model_name: Optional[str] = None, temperature: float = 0.2):
    """
    Return a chat model exposing `.with_structured_output(schema, method=...)`
    and `.invoke(...)`, i.e. a LangChain BaseChatModel.
    """
    # --- ADAPT START ---
    from langchain_mistralai import ChatMistralAI  # noqa: F401
    return ChatMistralAI(
        model=model_name or "mistral-large-latest",
        temperature=temperature,
    )
    # --- ADAPT END ---


def build_independent_critic():
    """
    A DIFFERENT model from build_model(), for the independent-critic ablation
    the brief asks for ("test how making an independent critic (a different LLM)
    would change the evaluation").
    """
    # --- ADAPT START ---
    return build_model(model_name="mistral-small-latest", temperature=0.0)
    # --- ADAPT END ---


# --------------------------------------------------------------------------- #
# 2. Cost / call accounting
# --------------------------------------------------------------------------- #
# The comparison table needs calls, tokens, latency and cost per run. Rather
# than instrumenting seven algorithm files, wrap the model object once: every
# algorithm goes through it, so every call is counted regardless of which search
# loop made it.

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
    Transparent proxy that counts calls and tokens.

    Wraps any LangChain chat model, including the object returned by
    .with_structured_output(), so structured calls are metered too.
    """

    def __init__(self, inner: Any, usage: Usage) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_usage", usage)

    def _meter(self, fn: Callable, *a, **kw):
        u: Usage = object.__getattribute__(self, "_usage")
        t0 = time.perf_counter()
        out = fn(*a, **kw)
        u.seconds += time.perf_counter() - t0
        u.calls += 1
        meta = getattr(out, "usage_metadata", None) or getattr(
            out, "response_metadata", {}).get("token_usage", {})
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
def metered(model_name: Optional[str] = None):
    """`with metered() as (model, usage): ...` — usage is filled in on exit."""
    usage = Usage()
    yield MeteredModel(build_model(model_name), usage), usage


# --------------------------------------------------------------------------- #
# 3. Entry points
# --------------------------------------------------------------------------- #
# Thin pass-throughs. The ADAPT blocks are where fork signatures differ.
# `python -m planning.toolkit_bridge --introspect` prints the truth.

def run_decomposition_first(request: str, model, *, environment=None, **kw):
    """algorithms/decomposition.py — full plan up front, topological execution."""
    m = load("decomposition")
    # --- ADAPT START ---
    fn = _first_callable(m, ["run", "run_decomposition", "decompose_and_execute",
                             "execute", "main"])
    return _call(fn, request=request, model=model, environment=environment, **kw)
    # --- ADAPT END ---


def run_dynamic_decomposition(request: str, model, *, environment=None, **kw):
    """algorithms/dynamic_decomposition.py — next sub-task after each observation."""
    m = load("dynamic_decomposition")
    fn = _first_callable(m, ["run", "run_dynamic", "dynamic_decompose",
                             "execute", "main"])
    return _call(fn, request=request, model=model, environment=environment, **kw)


def run_plan_and_solve(task: str, model, **kw):
    m = load("plan_and_solve")
    fn = _first_callable(m, ["run", "plan_and_solve", "solve", "main"])
    return _call(fn, task=task, model=model, **kw)


def run_tree_of_thoughts(task: str, model, *, depth: int = 2,
                         beam_width: int = 2, **kw):
    m = load("tree_of_thoughts")
    fn = _first_callable(m, ["run", "tree_of_thoughts", "search", "main"])
    return _call(fn, task=task, model=model, depth=depth,
                 beam_width=beam_width, **kw)


def run_lats(task: str, model, environment, *, iterations: int = 2,
             n_actions: int = 2, **kw):
    """
    algorithms/lats.py. `environment` MUST be a VelloraEnvironment for any run
    you report as grounded. Passing the toolkit default here and calling it
    grounded is the exact failure the guardrails describe.
    """
    m = load("lats")
    fn = _first_callable(m, ["run", "lats", "search", "main"])
    return _call(fn, task=task, model=model, environment=environment,
                 iterations=iterations, n_actions=n_actions, **kw)


def run_self_refine(task: str, model, *, critic=None, rubric: str = "", **kw):
    m = load("self_refine")
    fn = _first_callable(m, ["run", "self_refine", "refine", "main"])
    return _call(fn, task=task, model=model, critic=critic, rubric=rubric, **kw)


def run_reflexion(task: str, model, environment, *, max_trials: int = 3,
                  memory_size: int = 2, **kw):
    """memory_size=0 is the ablation that proves the episodic buffer does work."""
    m = load("reflexion")
    fn = _first_callable(m, ["run", "reflexion", "main"])
    return _call(fn, task=task, model=model, environment=environment,
                 max_trials=max_trials, memory_size=memory_size, **kw)


# --------------------------------------------------------------------------- #
# Tolerant dispatch helpers
# --------------------------------------------------------------------------- #

def _first_callable(module, names: List[str]):
    for n in names:
        fn = getattr(module, n, None)
        if callable(fn):
            return fn
    public = [n for n, o in vars(module).items()
              if callable(o) and not n.startswith("_")]
    raise AttributeError(
        f"{module.__name__}: none of {names} found. Public callables: {public}. "
        f"Update the ADAPT block in planning/toolkit_bridge.py."
    )


def _call(fn, **kwargs):
    """Drop kwargs the target doesn't accept, so signature drift degrades loudly
    but doesn't crash on an unrelated parameter name."""
    sig = inspect.signature(fn)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD
           for p in sig.parameters.values()):
        return fn(**{k: v for k, v in kwargs.items() if v is not None})
    accepted = set(sig.parameters)
    dropped = {k for k, v in kwargs.items() if k not in accepted and v is not None}
    if dropped:
        print(f"[toolkit_bridge] {fn.__qualname__} does not accept {sorted(dropped)}"
              f" — check the ADAPT block. Accepted: {sorted(accepted)}")
    return fn(**{k: v for k, v in kwargs.items()
                 if k in accepted and v is not None})


# --------------------------------------------------------------------------- #
# Introspection
# --------------------------------------------------------------------------- #

def introspect() -> None:
    print("Toolkit API as actually present in your fork:\n")
    for key, path in MODULES.items():
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
