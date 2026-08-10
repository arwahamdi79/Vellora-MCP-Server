# context_eval/benchmark.py
"""
Long-context benchmark for the four context-management strategies in
memory.short_term_memory.ShortTermMemory:

    - sliding_window
    - observation_masking
    - recursive_summarization
    - zone_based_pruning

For each strategy, at each conversation length, we measure:
    - messages_kept       how many messages survive pruning
    - est_tokens_kept      rough token estimate of what's kept (4 chars/token)
    - compression_ratio   est_tokens_kept / est_tokens_original
    - key_facts_retained  how many of the 2 planted safety-critical facts
                           are still present in the kept content (0, 1, or 2)
    - latency_ms          wall-clock time to run the strategy

Run directly: `python -m context_eval.benchmark`
Writes context_eval/results.csv and prints a markdown comparison table.
"""

import csv
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from memory.short_term_memory import ShortTermMemory, Message
from .scenarios import build_conversation, key_fact_survival


# ---------------------------------------------------------------------------
# Stand-in summarizer
# ---------------------------------------------------------------------------
# recursive_summarization takes a summarizer_func(text) -> str. In production
# this is an LLM call; here we use a cheap extractive stand-in so the
# strategy's *mechanics* (splitting, budget-fitting, replacing old messages
# with one summary block) can be benchmarked without a live model. Swap this
# for a real LLM call in agent/rag_adapter.py-style wiring when one is
# available.
_SIGNAL_KEYWORDS = ('fail', 'recall', 'contaminat', 'reject', 'critical', 'do not')


def extractive_summarizer(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    signal = [s for s in sentences if any(k in s.lower() for k in _SIGNAL_KEYWORDS)]
    filler_sample = sentences[-2:] if len(sentences) > 2 else sentences
    kept = signal + [s for s in filler_sample if s not in signal]
    return " ".join(kept)[:800]


# ---------------------------------------------------------------------------
# Strategy runners
# ---------------------------------------------------------------------------

def _content_of(item: Any) -> str:
    if isinstance(item, Message):
        return item.content
    if isinstance(item, dict):
        return item.get('content', '')
    return str(item)


def _estimate_tokens(texts: List[str]) -> int:
    return sum(len(t) // 4 for t in texts)


STRATEGIES = {
    'sliding_window': dict(window_size=15),
    'observation_masking': dict(keep_tool_outputs=3),
    'recursive_summarization': dict(max_tokens=800, summarizer_func=extractive_summarizer),
    'zone_based_pruning': dict(zones={'system': 999, 'user': 4, 'assistant': 4, 'tool': 3}),
}


def run_one(strategy_name: str, kwargs: Dict[str, Any], n_messages: int, seed: int) -> Dict[str, Any]:
    messages = build_conversation(n_messages, seed=seed)

    stm = ShortTermMemory(max_size=n_messages)  # no eviction while loading the scenario
    for m in messages:
        stm.messages.append(m)

    original_tokens = _estimate_tokens([m.content for m in messages])

    start = time.perf_counter()
    kept = stm.apply_strategy(strategy_name, **kwargs)
    latency_ms = (time.perf_counter() - start) * 1000

    kept_texts = [_content_of(item) for item in kept]
    kept_tokens = _estimate_tokens(kept_texts)
    facts_found, facts_total = key_fact_survival(kept_texts)

    return {
        'strategy': strategy_name,
        'n_messages': n_messages,
        'messages_kept': len(kept),
        'est_tokens_original': original_tokens,
        'est_tokens_kept': kept_tokens,
        'compression_ratio': round(kept_tokens / original_tokens, 3) if original_tokens else 0,
        'key_facts_retained': f"{facts_found}/{facts_total}",
        'latency_ms': round(latency_ms, 3),
    }


def run_benchmark(conversation_lengths: List[int] = (20, 50, 100, 200), seed: int = 42) -> List[Dict[str, Any]]:
    rows = []
    for n in conversation_lengths:
        for strategy_name, kwargs in STRATEGIES.items():
            rows.append(run_one(strategy_name, kwargs, n, seed))
    return rows


def write_csv(rows: List[Dict[str, Any]], path: Path):
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_markdown_table(rows: List[Dict[str, Any]]):
    headers = ['strategy', 'n_messages', 'messages_kept', 'compression_ratio', 'key_facts_retained', 'latency_ms']
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        print("| " + " | ".join(str(row[h]) for h in headers) + " |")


def main():
    rows = run_benchmark()
    out_path = Path(__file__).parent / 'results.csv'
    write_csv(rows, out_path)
    print(f"Wrote {len(rows)} rows to {out_path}\n")
    print_markdown_table(rows)


if __name__ == '__main__':
    main()