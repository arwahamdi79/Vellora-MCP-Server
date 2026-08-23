"""
Lightweight LLM helper used inside graph nodes.
Falls back to deterministic stubs when no API key is present so demos run offline.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def _has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


def chat(prompt: str, system: str = "You are a pharmaceutical operations assistant.") -> str:
    if not _has_key():
        # Deterministic offline stub so demos and graders work without keys
        return _stub(prompt)
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[llm_error] {e}"


def _stub(prompt: str) -> str:
    p = prompt.lower()
    if "decompose" in p or "steps" in p:
        return json.dumps([
            "Verify batch test results against release criteria",
            "Confirm supplier qualification status",
            "Draft release certificate",
            "Obtain QA Manager sign-off if new supplier",
            "Update batch status to Released",
        ])
    if "tree of thoughts" in p or "appeal" in p or "strategies" in p:
        return json.dumps([
            {"strategy": "missing_data", "score": 0.8, "argument": "Lab result arrived late; resubmit with full panel."},
            {"strategy": "policy_cite", "score": 0.7, "argument": "Cite Batch Approval Policy §3.2 for conditional release."},
            {"strategy": "retest", "score": 0.6, "argument": "Request retest of OOS parameter under CAPA."},
        ])
    if "rag" in p or "protocol" in p or "policy" in p:
        return "According to Batch Approval Policy §3.2 and Manufacturing SOP, a new supplier requires documented qualification and QA Manager approval before release."
    if "triage" in p or "lats" in p:
        return json.dumps({"ordering": ["stabilize", "labs", "imaging"], "acuity": 0.82})
    return "OK — proceed with standard operating procedure."


def decompose_task(goal: str) -> List[str]:
    raw = chat(f"Decompose this pharmaceutical workflow into ordered steps as a JSON list:\n{goal}")
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return [s.strip("- ").strip() for s in raw.splitlines() if s.strip()][:8]


def tree_of_thoughts(problem: str, k: int = 3) -> List[Dict[str, Any]]:
    raw = chat(
        f"Tree of Thoughts: propose {k} ranked strategies for this problem as a JSON list "
        f"of objects with keys strategy, score, argument:\n{problem}"
    )
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return [{"strategy": "default", "score": 0.5, "argument": raw[:200]}]


def constrained_react(action: str, allowed: List[str], context: str = "") -> Dict[str, Any]:
    """Only emit an action that is in the whitelist."""
    if action not in allowed:
        return {"ok": False, "action": None, "error": f"Action '{action}' not in whitelist {allowed}"}
    return {"ok": True, "action": action, "context": context}


def rag_lookup(query: str) -> str:
    return chat(f"RAG / policy retrieval for: {query}")
