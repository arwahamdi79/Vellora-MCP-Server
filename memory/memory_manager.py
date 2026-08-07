# memory/memory_manager.py
"""
Memory Manager - orchestrates all memory components.
Provides a unified interface for the agent.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .short_term_memory import ShortTermMemory, Scratchpad
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory
from .promote_drop_router import PromoteDropRouter
from .consolidation import ConsolidationLayer


logger = logging.getLogger(__name__)


class MemoryManager:
    """Central orchestrator for short-term, episodic, and semantic memory."""

    def __init__(self,
                 short_term_max_size: int = 100,
                 storage_path: Optional[str] = None,
                 importance_threshold: float = 0.6,
                 consolidation_interval_hours: int = 24):

        self.short_term = ShortTermMemory(max_size=short_term_max_size)
        self.episodic = EpisodicMemory(storage_path=storage_path)
        self.semantic = SemanticMemory()

        self.router = PromoteDropRouter(
            episodic_memory=self.episodic,
            importance_threshold=importance_threshold,
        )

        self.consolidation = ConsolidationLayer(
            episodic_memory=self.episodic,
            semantic_memory=self.semantic,
            router=self.router,
        )

        self._consolidation_interval_hours = consolidation_interval_hours
        self._last_consolidation: Optional[datetime] = None
        self._session_id: str = ""
        self._user_id: str = ""

    # ===== Session Management =====

    def start_session(self, session_id: str, user_id: str):
        self._session_id = session_id
        self._user_id = user_id
        self.short_term.clear()
        self.short_term.scratchpad = Scratchpad()
        logger.info("Session started: %s for user %s", session_id, user_id)

    def end_session(self):
        if self.short_term.messages:
            self._route_messages()
        self._check_consolidation(force=True)
        logger.info("Session ended: %s", self._session_id)
        self._session_id = ""
        self._user_id = ""

    # ===== Message Management =====

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a message to short-term memory, routing the current buffer first if it's
        already full. `short_term.messages` is a maxlen deque, so appending to a full
        buffer silently evicts the oldest message before it can ever be routed to
        episodic memory - routing here, before the append, avoids that data loss.
        """
        if len(self.short_term.messages) >= self.short_term.max_size:
            self._route_messages()
        return self.short_term.add_message(role, content, metadata)

    def update_scratchpad(self, **kwargs):
        self.short_term.scratchpad.update(**kwargs)

    def add_scratchpad_note(self, note: str):
        self.short_term.scratchpad.add_note(note)

    # ===== Context Management =====

    def get_context(self, strategy: str = 'sliding_window', **kwargs) -> str:
        """
        Build the full prompt context: semantic facts + recent episodes + short-term
        buffer (pruned via `strategy`: sliding_window, observation_masking,
        recursive_summarization, or zone_based_pruning).
        """
        semantic_context = self._get_semantic_context()
        episodic_context = self._get_episodic_context()
        short_term_context = self.short_term.get_context_for_prompt(strategy, **kwargs)
        return f"{semantic_context}\n\n{episodic_context}\n\n{short_term_context}"

    def _get_semantic_context(self) -> str:
        facts = sorted(self.semantic.get_active_facts(), key=lambda f: f.confidence, reverse=True)
        if not facts:
            return "=== SEMANTIC MEMORY ===\nNo relevant facts in semantic memory."

        lines = ["=== SEMANTIC MEMORY ==="]
        lines += [f"[{f.category}] {f.statement} (confidence: {f.confidence:.2f})" for f in facts[:10]]
        return "\n".join(lines)

    def _get_episodic_context(self) -> str:
        episodes = self.episodic.get_recent_episodes(5, self._user_id)
        if not episodes:
            return "=== EPISODIC MEMORY ===\nNo recent episodes."

        lines = ["=== EPISODIC MEMORY ==="] + [f"* {e.summary}" for e in episodes]
        return "\n".join(lines)

    # ===== Routing =====

    def _route_messages(self):
        """Route messages from short-term to episodic memory, then clear the buffer."""
        if not self.short_term.messages:
            return

        items = list(self.short_term.messages)
        context = {
            'session_id': self._session_id,
            'user_id': self._user_id,
            'goal_matches': bool(self.short_term.scratchpad.plan),
            'critical_keywords': self._extract_critical_keywords(),
            'novel': self._is_novel_content(items),
        }

        decisions, promoted = self.router.route_items(items, context)
        logger.info(
            "Routed %d items: %d promoted, %d forgotten, %d deferred",
            len(items),
            sum(1 for d in decisions if d.decision == 'promote'),
            sum(1 for d in decisions if d.decision == 'forget'),
            sum(1 for d in decisions if d.decision == 'defer'),
        )

        self.short_term.clear()
        self._check_consolidation()

    def _extract_critical_keywords(self) -> List[str]:
        """Words (len > 4) that show up at least 3 times in the current buffer."""
        counts: Dict[str, int] = {}
        for msg in self.short_term.messages:
            for word in msg.content.lower().split():
                if len(word) > 4:
                    counts[word] = counts.get(word, 0) + 1
        return [word for word, count in counts.items() if count >= 3][:10]

    def _is_novel_content(self, items: List[Any]) -> bool:
        """An item batch counts as novel if it overlaps <30% with recent episodes."""
        recent = self.episodic.get_recent_episodes(3)
        if not recent:
            return True

        recent_text = " ".join(e.summary for e in recent)
        item_text = " ".join(str(self.router._get_item_content(item)) for item in items[-3:])

        words1 = set(item_text.lower().split())
        words2 = set(recent_text.lower().split())
        if not words1:
            return False

        overlap = len(words1 & words2) / len(words1 | words2)
        return overlap < 0.3

    # ===== Consolidation =====

    def _check_consolidation(self, force: bool = False):
        if force or self._last_consolidation is None:
            self._run_consolidation()
            return

        hours_since = (datetime.now() - self._last_consolidation).total_seconds() / 3600
        if hours_since >= self._consolidation_interval_hours:
            self._run_consolidation()

    def _run_consolidation(self) -> Dict[str, Any]:
        logger.info("Running consolidation...")
        results = self.consolidation.run_consolidation()
        self._last_consolidation = datetime.now()
        logger.info("Consolidation complete: %s", results)
        return results

    def run_consolidation_now(self) -> Dict[str, Any]:
        """Force consolidation immediately."""
        return self._run_consolidation()

    # ===== Search =====

    def search_memory(self, query: str, n: int = 5) -> Dict[str, Any]:
        """Search across all three memory tiers."""
        query_lower = query.lower()
        return {
            'semantic': [f.to_dict() for f in self.semantic.search_facts(query, n)],
            'episodic': [e.to_dict() for e in self.episodic.search_episodes(query, n)],
            'short_term': [
                m.to_dict() for m in self.short_term.messages if query_lower in m.content.lower()
            ],
        }

    # ===== Statistics =====

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'short_term': {
                'size': len(self.short_term.messages),
                'max_size': self.short_term.max_size,
            },
            'episodic': {'count': self.episodic.count()},
            'semantic': {
                'total': self.semantic.count(),
                'active': self.semantic.count_active(),
            },
            'routing': self.router.get_statistics(),
            'consolidation': self.consolidation.get_statistics(),
            'session': {
                'session_id': self._session_id,
                'user_id': self._user_id,
                'last_consolidation': (
                    self._last_consolidation.isoformat() if self._last_consolidation else None
                ),
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export entire memory state."""
        return {
            'short_term': self.short_term.to_dict(),
            'episodic': self.episodic.to_dict(),
            'semantic': self.semantic.to_dict(),
            'routing_decisions': self.router.get_decision_log(50),
            'consolidation_history': self.consolidation.get_history(),
            'statistics': self.get_statistics(),
        }