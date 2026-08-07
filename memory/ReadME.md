# Vellora Memory & Context System

Short-term/episodic/semantic memory with promote-or-drop routing and periodic
consolidation, four context-management strategies benchmarked for
long-conversation safety, and the integration layer wiring both (plus RAG)
into the Vellora MCP agent.

## Status — Member 3 (Context & Integration Engineer)

| Task | Status | Notes |
|---|---|---|
| Sliding window | ✅ | `context_eval/benchmark.py`, implemented in `memory/short_term_memory.py` |
| Observation masking | ✅ | same |
| Recursive summarization | ✅ | same — summarizer is dependency-injected, not hardcoded |
| Zone-based pruning | ✅ | same |
| Long-context benchmark | ✅ | `context_eval/benchmark.py` → `context_eval/results.csv`, run at 20/50/100/200-message conversation lengths |
| Context comparison table | ✅ | `context_eval/README.md` |
| Memory + RAG integration | ✅ | `agent/agent.py` (`VelloraAgent`), `agent/memory_adapter.py`, `agent/rag_adapter.py` |
| Update README | ✅ | this file, plus `agent/README.md` and `context_eval/README.md` |
| Prepare demo | ✅ | `python -m agent.demo` — memory is real (`MemoryManager`), RAG is mocked (`MockPolicyRAG`) since this dev environment has no network path to HuggingFace or an LLM; see [Known gaps](#known-gaps) |

## Layout

```
memory/         Short-term, episodic, semantic memory; promote/drop router; consolidation
context_eval/   Benchmark comparing the four context strategies + results
agent/          Integration layer: memory adapter, RAG adapter, orchestrator, demo
```

## Setup

No dependencies beyond the Python standard library for `memory/`,
`context_eval/`, and `agent/demo.py`. `agent/rag_adapter.py` additionally
needs the existing `rag/` package plus its dependencies (`langchain`,
`chromadb`, `sentence-transformers`) and a real LLM — only required if you
call `build_rag()`.

## Running it

Run all commands from the directory containing `memory/`, `context_eval/`,
and `agent/` (they use package-style imports, so `-m`, not direct script
execution):

```bash
# Memory system tests — contradictions, duplicates, buffer overflow,
# scratchpad, router reasoning, full pipeline (7 tests)
python -m memory.quick_test

# Context strategy benchmark — prints a comparison table, writes results.csv
python -m context_eval.benchmark

# Full integration demo — memory + context strategy + (mocked) RAG, end to end
python -m agent.demo
```

## Integrating into the MCP server

In `mcp_server/tools.py`, replace:

```python
from .memory.episodic_memory import maybe_remember, load_memory_context
```

with:

```python
from agent.memory_adapter import maybe_remember, load_memory_context
```

No other changes needed — call sites are unchanged. See `agent/README.md`
for the full integration flow and the bugs this integration work surfaced
and fixed in the memory package.



## Further reading

- `context_eval/README.md` — full benchmark results and strategy trade-off analysis
- `agent/README.md` — integration details, migration diff, bugs found and fixed
