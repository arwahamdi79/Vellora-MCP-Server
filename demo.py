# agent/demo.py
"""
End-to-end demo of the Member 3 integration: memory + context strategies +
RAG, wired together in VelloraAgent.

Run: python -m agent.demo

What's real vs. mocked here:
  - Memory (MemoryManager, ShortTermMemory strategies, promote/drop routing,
    consolidation) is the actual implementation - fully exercised below.
  - RAG is a MockPolicyRAG standing in for agent.rag_adapter.PolicyRAG,
    because this sandbox can't reach HuggingFace (for embeddings) or an LLM
    API. It implements the same `.ask(query) -> response` interface, so the
    *pipeline* (agent.handle_turn calling self.rag.ask() and stitching the
    result into the prompt) is genuinely exercised - only the retrieval
    quality is fake. Swap `MockPolicyRAG()` for
    `rag_adapter.build_rag(real_llm, bm25_chunks=...)` in production; nothing
    else in VelloraAgent changes.
"""

from types import SimpleNamespace

from .agent import VelloraAgent


class MockPolicyRAG:
    """
    Stand-in for agent.rag_adapter.PolicyRAG. Keyword-matches the query
    against a tiny in-memory policy snippet set instead of doing real vector
    retrieval - just enough to prove the retrieval -> prompt-assembly wiring
    works without a live embedding model or LLM.
    """

    _DOCS = {
        'batch approval qa review': (
            "Batches must pass two independent QA reviews before status can move to 'Approved'.",
            'batch_approval_policy.md',
        ),
        'recall contamination distribute': (
            "Any batch with a failed contamination test must be recalled within 24 hours of the test result.",
            'product_recall_policy.md',
        ),
        'storage temperature cold chain': (
            "Temperature-sensitive medicines must be stored below 8 degrees Celsius at all times.",
            'storage_guidelines.md',
        ),
    }

    def ask(self, query: str):
        query_lower = query.lower()
        best_key = max(
            self._DOCS,
            key=lambda k: sum(1 for word in k.split() if word in query_lower),
        )
        answer, source = self._DOCS[best_key]
        chunk = SimpleNamespace(source=source)
        return SimpleNamespace(
            answer=answer,
            retrieved_chunks=[chunk],
            metadata=SimpleNamespace(confidence=0.75),
        )


def section(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main():
    agent = VelloraAgent(rag=MockPolicyRAG(), context_strategy='zone_based_pruning')
    agent.start_session(session_id='demo_session', user_id='qa_manager_204')

    # --- Simulate MCP tool events firing during the session ---------------
    section("Tool events (as change_batch_status / add_quality_test would emit)")
    r1 = agent.record_tool_event(
        turn_text="Batch 1042\nStatus changed to: Pending QA",
        entity_id="batch_1042",
    )
    print("record_tool_event (status change):", r1)

    r2 = agent.record_tool_event(
        turn_text=(
            "Batch 1042\n"
            "Test: Contamination Screen\n"
            "Result: Fail\n"
            "Remarks: Contamination detected in Line 3, recommend recall."
        ),
        entity_id="batch_1042",
    )
    print("record_tool_event (QA test):", r2)

    # --- A normal conversational turn: memory + RAG + prompt assembly -----
    section("handle_turn: policy question (memory + RAG)")
    result = agent.handle_turn("What's our policy on batch recalls after a contamination failure?")
    print("RAG answer:      ", result.rag_answer)
    print("RAG confidence:  ", result.rag_confidence)
    print("Sources:         ", result.retrieved_sources)
    print("\n--- Assembled prompt sent to the LLM ---\n")
    print(result.prompt)

    # --- Force consolidation (periodic in production; forced here for the demo) ---
    # Note: consolidation ran automatically after the first tool event (see
    # memory_adapter.maybe_remember), but only because _last_consolidation was
    # still None. The second event (the actual contamination failure) won't be
    # distilled into a semantic fact until the next scheduled pass, by design -
    # consolidation.py is explicit that it "runs periodically, never at write
    # time." Forcing it here shows the operator-triggered path.
    section("Forcing a consolidation pass (would normally run on its interval)")
    from .memory_adapter import get_manager
    manager = get_manager("batch_1042")
    consolidation_results = manager.run_consolidation_now()
    print("facts_created:", consolidation_results.get('facts_created'))
    print("facts_updated:", consolidation_results.get('facts_updated'))

    # --- get_batch_memory-style lookup for the entity we just touched -----
    section("get_batch_memory equivalent: load_memory_context('batch_1042', ...)")
    from .memory_adapter import load_memory_context
    memory_lookup = load_memory_context(
        entity_id="batch_1042",
        opening_message="Why was batch 1042 flagged?",
    )
    print("Related facts:   ", memory_lookup['related_facts'])
    print("Related episodes:", memory_lookup['related_episodes'])
    print("\n--- Context block ---\n")
    print(memory_lookup['context'])

    agent.end_session()


if __name__ == '__main__':
    main()