# agent/agent.py
"""
VelloraAgent - integrates memory, context-management strategies, and RAG
into a single turn-handling pipeline:

    User
      |
    VelloraAgent.handle_turn(user_message)
      |
    MemoryManager.get_context(strategy=...)   -> ShortTermMemory.apply_strategy()
      |
    PolicyRAG.ask(user_message)                -> rag.factory.RAGFactory pipeline
      |
    _build_prompt(memory_context, rag_answer, sources, user_message)
      |
    (returned to caller, which sends it to the LLM - the actual model call
     is intentionally outside this class, same dependency-injection pattern
     used for summarizer_func in ShortTermMemory.strategy_recursive_summarization)

RAG is optional: an agent built without one (`VelloraAgent()`) still runs
the full memory pipeline, it just skips the retrieval step. This lets the
memory half of the integration be demoed/tested without needing the
HuggingFace/LLM services PolicyRAG depends on (see agent/demo.py, which
uses a lightweight mock in place of PolicyRAG for exactly this reason).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from memory.memory_manager import MemoryManager
from .memory_adapter import maybe_remember


@dataclass
class AgentTurnResult:
    prompt: str
    memory_context: str
    retrieved_sources: List[str] = field(default_factory=list)
    rag_answer: Optional[str] = None
    rag_confidence: Optional[float] = None


class VelloraAgent:
    """Top-level orchestrator used by the MCP client loop for one user session."""

    def __init__(self,
                 rag: Optional[Any] = None,
                 context_strategy: str = 'zone_based_pruning',
                 memory_manager: Optional[MemoryManager] = None):
        self.memory = memory_manager or MemoryManager()
        self.rag = rag  # anything with .ask(query) -> object with .answer/.retrieved_chunks/.metadata.confidence
        self.context_strategy = context_strategy

    # ===== Session lifecycle =====

    def start_session(self, session_id: str, user_id: str):
        self.memory.start_session(session_id, user_id)

    def end_session(self):
        self.memory.end_session()

    # ===== Turn handling =====

    def handle_turn(self, user_message: str, **strategy_kwargs) -> AgentTurnResult:
        """Process one user turn: log it to memory, pull memory context under
        the configured strategy, optionally retrieve policy docs via RAG, and
        assemble the final prompt. Returns the assembled pieces rather than
        calling an LLM directly - the caller owns the actual model call."""
        self.memory.add_message('user', user_message)

        memory_context = self.memory.get_context(strategy=self.context_strategy, **strategy_kwargs)

        retrieved_sources: List[str] = []
        rag_answer: Optional[str] = None
        rag_confidence: Optional[float] = None

        if self.rag is not None:
            response = self.rag.ask(user_message)
            rag_answer = response.answer
            rag_confidence = response.metadata.confidence
            retrieved_sources = [chunk.source for chunk in response.retrieved_chunks]

        prompt = self._build_prompt(memory_context, rag_answer, retrieved_sources, user_message)

        return AgentTurnResult(
            prompt=prompt,
            memory_context=memory_context,
            retrieved_sources=retrieved_sources,
            rag_answer=rag_answer,
            rag_confidence=rag_confidence,
        )

    def _build_prompt(self, memory_context: str, rag_answer: Optional[str],
                       retrieved_sources: List[str], user_message: str) -> str:
        parts = [memory_context]
        if rag_answer:
            parts.append("=== POLICY RETRIEVAL ===\n" + rag_answer)
            if retrieved_sources:
                parts.append("Sources: " + ", ".join(retrieved_sources))
        parts.append(f"=== CURRENT USER MESSAGE ===\n{user_message}")
        return "\n\n".join(parts)

    # ===== Tool-event bridge =====

    def record_tool_event(self, turn_text: str, entity_id: str) -> Dict[str, Any]:
        """
        Called by MCP tools (change_batch_status, add_quality_test, ...) to
        log significant domain events - same call shape as the old
        maybe_remember(), routed through the same per-entity MemoryManager
        registry as agent.memory_adapter.load_memory_context, so a tool event
        recorded here is immediately visible to get_batch_memory.
        """
        return maybe_remember(turn_text=turn_text, entity_id=entity_id)