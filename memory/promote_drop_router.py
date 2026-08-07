# memory/promote_drop_router.py
"""
Promote-or-drop routing decision layer.
Decides what to forget and what to promote to episodic memory.
Does NOT write directly to semantic memory.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

from .short_term_memory import Message
from .episodic_memory import Episode, EpisodicMemory


logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Decision made by the router for an item."""

    item_id: str
    item_type: str  # 'message', 'interaction', 'observation'
    item_content: Any
    decision: str  # 'forget', 'promote', 'defer'
    reasoning: str
    importance_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'item_id': self.item_id,
            'item_type': self.item_type,
            'item_content': str(self.item_content)[:500],  # Truncate for logging
            'decision': self.decision,
            'reasoning': self.reasoning,
            'importance_score': self.importance_score,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context,
        }


class PromoteDropRouter:
    """
    Router that decides what to promote to episodic memory or forget.
    Fires when short-term memory overflows.
    """

    STOPWORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'for', 'of',
        'and', 'or', 'but', 'in', 'on', 'at', 'with', 'without', 'by',
        'from', 'up', 'about', 'into', 'through', 'during', 'including',
        'my', 'your', 'his', 'her', 'its', 'our', 'their', 'me', 'you',
        'him', 'us', 'them',
    }
    URGENCY_MARKERS = ('urgent', 'immediate', 'asap', 'quickly', 'emergency')
    DUPLICATE_SIMILARITY_THRESHOLD = 0.3

    def __init__(self,
                 episodic_memory: EpisodicMemory,
                 importance_threshold: float = 0.6,
                 max_promotions_per_batch: int = 5):
        self.episodic_memory = episodic_memory
        self.importance_threshold = importance_threshold
        self.max_promotions_per_batch = max_promotions_per_batch
        self._decision_log: List[RoutingDecision] = []

    def route_items(self,
                     items: List[Any],
                     context: Dict[str, Any] = None) -> Tuple[List[RoutingDecision], List[Episode]]:
        """Route multiple items from short-term memory. Returns (decisions, promoted_episodes)."""
        decisions = []
        promoted = []
        context = context or {}

        for item in items:
            decision = self._route_single(item, context)
            decisions.append(decision)

            if decision.decision == 'promote':
                episode = self._create_episode(item, decision, context)
                self.episodic_memory.add_episode(episode)
                promoted.append(episode)

                if len(promoted) >= self.max_promotions_per_batch:
                    logger.info("Reached max promotions (%d), stopping", self.max_promotions_per_batch)
                    break

        self._decision_log.extend(decisions)
        return decisions, promoted

    def _route_single(self, item: Any, context: Dict[str, Any]) -> RoutingDecision:
        """
        Route a single item based on importance, recency, goal relevance, and novelty.
        """
        importance = self._calculate_importance(item, context)
        should_promote = importance >= self.importance_threshold

        if should_promote and self._is_duplicate(item, context):
            importance *= 0.7
            should_promote = importance >= self.importance_threshold

        reasoning_parts = [
            f"Importance score: {importance:.2f}",
            f"Threshold: {self.importance_threshold:.2f}",
        ]

        if should_promote:
            decision = 'promote'
            reasoning_parts.append("Promoting to episodic memory: item exceeds importance threshold")
            if context.get('goal_matches'):
                reasoning_parts.append("Matches current goal")
            if context.get('novel'):
                reasoning_parts.append("Contains novel information")
        elif importance > 0.3 and context.get('can_defer'):
            decision = 'defer'
            reasoning_parts.append("Deferring: may become important later")
        else:
            decision = 'forget'
            reasoning_parts.append("Forgetting: below importance threshold")

        return RoutingDecision(
            item_id=self._get_item_id(item),
            item_type=self._get_item_type(item),
            item_content=self._get_item_content(item),
            decision=decision,
            reasoning="; ".join(reasoning_parts),
            importance_score=importance,
            context=context,
        )

    def _calculate_importance(self, item: Any, context: Dict[str, Any]) -> float:
        """
        Score factors: content length, critical keywords, urgency language,
        goal relevance, novelty, and message role.
        """
        score = 0.3  # Base score
        content = str(self._get_item_content(item))
        content_lower = content.lower()

        if len(content) > 500:
            score += 0.15
        elif len(content) > 200:
            score += 0.08

        for keyword in context.get('critical_keywords', []):
            if keyword.lower() in content_lower:
                score += 0.1

        if any(marker in content_lower for marker in self.URGENCY_MARKERS):
            score += 0.1

        if context.get('goal_matches'):
            score += 0.15
        if context.get('novel'):
            score += 0.1

        if isinstance(item, Message):
            if item.role == 'user':
                score += 0.1
            elif item.role == 'tool' and 'error' in content_lower:
                score += 0.15
            elif item.role == 'assistant':
                score += 0.05

        return min(score, 1.0)

    def _create_episode(self, item: Any, decision: RoutingDecision, context: Dict[str, Any]) -> Episode:
        """Create an episode from a promoted item."""
        content = str(self._get_item_content(item))
        item_type = self._get_item_type(item)

        tags = set(context.get('critical_keywords', []))

        summary = f"{item_type}: {content[:200]}..."
        if 'user_id' in context:
            summary = f"User {context['user_id']}: {summary}"

        return Episode(
            summary=summary,
            details={
                'original_item': item.to_dict() if hasattr(item, 'to_dict') else str(item),
                'item_type': item_type,
                'routing_decision': decision.to_dict(),
                'context': context,
            },
            importance_score=decision.importance_score,
            tags=tags,
            extracted_facts=self._extract_facts(content),
            context={'decision': decision.to_dict()},
            session_id=context.get('session_id', ''),
            user_id=context.get('user_id', ''),
        )

    def _extract_facts(self, content: str) -> List[str]:
        """Pull out plausible declarative-statement sentences for later consolidation."""
        facts = []
        for sentence in content.split('.'):
            sentence = sentence.strip()
            if len(sentence) > 20 and any(
                kw in sentence.lower() for kw in ('is', 'are', 'was', 'were', 'has', 'have')
            ):
                facts.append(sentence)
        return facts[:5]

    def _get_item_id(self, item: Any) -> str:
        if hasattr(item, 'message_id'):
            return item.message_id
        if hasattr(item, 'id'):
            return str(item.id)
        return f"item_{hash(str(item))}"

    def _get_item_type(self, item: Any) -> str:
        if isinstance(item, Message):
            return f"message_{item.role}"
        return type(item).__name__.lower()

    def _get_item_content(self, item: Any) -> str:
        if isinstance(item, Message):
            return item.content
        if hasattr(item, 'content'):
            return str(item.content)
        return str(item)

    def _is_duplicate(self, item: Any, context: Dict[str, Any]) -> bool:
        """Check if this item closely overlaps a recent episode (word-overlap heuristic)."""
        content = str(self._get_item_content(item)).lower()
        content_words = {w for w in content.split() if len(w) > 3 and w not in self.STOPWORDS}
        if not content_words:
            return False

        for episode in self.episodic_memory.get_recent_episodes(15):
            episode_text = (episode.summary + " " + str(episode.details)).lower()
            episode_words = {w for w in episode_text.split() if len(w) > 3 and w not in self.STOPWORDS}
            if not episode_words:
                continue

            common = content_words & episode_words
            if len(common) < 2:
                continue

            similarity = len(common) / max(len(content_words), len(episode_words))
            if similarity > self.DUPLICATE_SIMILARITY_THRESHOLD:
                return True

        return False

    def get_decision_log(self, n: int = 100) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._decision_log[-n:]]

    def clear_decision_log(self):
        self._decision_log.clear()

    def get_statistics(self) -> Dict[str, Any]:
        decisions = self._decision_log
        if not decisions:
            return {'total': 0}

        promoted = sum(1 for d in decisions if d.decision == 'promote')
        forgotten = sum(1 for d in decisions if d.decision == 'forget')
        deferred = sum(1 for d in decisions if d.decision == 'defer')

        return {
            'total': len(decisions),
            'promoted': promoted,
            'forgotten': forgotten,
            'deferred': deferred,
            'promotion_rate': promoted / len(decisions),
            'avg_importance': sum(d.importance_score for d in decisions) / len(decisions),
        }