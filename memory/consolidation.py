# memory/consolidation.py
"""
Semantic memory consolidation layer.
Periodic pass over episodic memory to build semantic facts.
Handles updates, versioning, expiration, and conflicts.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from .episodic_memory import Episode, EpisodicMemory
from .semantic_memory import SemanticMemory, Fact
from .promote_drop_router import PromoteDropRouter
from .contradiction import same_topic, are_contradictory


logger = logging.getLogger(__name__)


class ConsolidationLayer:
    """
    Consolidates episodic memories into semantic facts.
    Runs periodically, never at write time. Handles contradictions explicitly.
    """

    def __init__(self,
                 episodic_memory: EpisodicMemory,
                 semantic_memory: SemanticMemory,
                 router: PromoteDropRouter,
                 min_importance: float = 0.5,
                 max_facts_per_run: int = 20,
                 similarity_threshold: float = 0.7):
        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.router = router
        self.min_importance = min_importance
        self.max_facts_per_run = max_facts_per_run
        self.similarity_threshold = similarity_threshold
        self._last_run: Optional[datetime] = None
        self._run_history: List[Dict[str, Any]] = []

    def run_consolidation(self,
                           since: Optional[datetime] = None,
                           force_full: bool = False) -> Dict[str, Any]:
        """Run the consolidation pass."""
        logger.info("Starting consolidation pass")

        if since is None and self._last_run:
            since = self._last_run

        episodes = self.episodic_memory.get_episodes_for_consolidation(
            since=since,
            min_importance=0 if force_full else self.min_importance,
        )

        if not episodes:
            logger.info("No episodes to consolidate")
            return {
                'status': 'no_episodes',
                'episodes_processed': 0,
                'facts_created': 0,
                'facts_updated': 0,
                'facts_expired': 0,
                'contradictions_resolved': 0,
                'contradictions_found': 0,
            }

        results = {
            'episodes_processed': len(episodes),
            'facts_created': 0,
            'facts_updated': 0,
            'facts_expired': 0,
            'contradictions_resolved': 0,
            'contradictions_found': 0,
            'skipped_duplicates': 0,
            'created_facts': [],
            'updated_facts': [],
            'resolved_contradictions': [],
        }

        grouped = self._group_episodes(episodes)

        for topic, group_episodes in grouped.items():
            if len(results['created_facts']) >= self.max_facts_per_run:
                break

            facts = self._extract_facts_from_episodes(group_episodes, topic)

            for fact_info in facts:
                fact_result = self._process_fact(fact_info)

                if fact_result['status'] == 'created':
                    results['facts_created'] += 1
                    results['created_facts'].append(fact_result['fact'])
                    if fact_result.get('contradiction_flagged'):
                        results['contradictions_found'] += 1
                elif fact_result['status'] == 'updated':
                    results['facts_updated'] += 1
                    results['updated_facts'].append(fact_result['fact'])
                    if fact_result.get('contradiction_resolved'):
                        results['contradictions_resolved'] += 1
                        results['resolved_contradictions'].append(fact_result)
                elif fact_result['status'] == 'skipped':
                    if fact_result.get('reason') == 'contradiction_resolved':
                        results['contradictions_found'] += 1
                    else:
                        results['skipped_duplicates'] += 1

        # Also check for contradictions among facts already in semantic memory
        for contradiction in self.semantic_memory.find_contradictions():
            resolved = self._resolve_contradiction(contradiction)
            if resolved:
                results['contradictions_resolved'] += 1
                results['resolved_contradictions'].append(resolved)

        self._last_run = datetime.now()
        self._run_history.append({
            'timestamp': self._last_run.isoformat(),
            'results': results,
        })

        logger.info(
            "Consolidation complete: %d created, %d updated, %d contradictions resolved",
            results['facts_created'], results['facts_updated'], results['contradictions_resolved'],
        )

        return results

    # ===== Extraction =====

    def _group_episodes(self, episodes: List[Episode]) -> Dict[str, List[Episode]]:
        """Group episodes by tag, falling back to context category."""
        groups: Dict[str, List[Episode]] = {}
        for episode in episodes:
            if episode.tags:
                for tag in episode.tags:
                    groups.setdefault(tag, []).append(episode)
            else:
                category = episode.context.get('category', 'general')
                groups.setdefault(category, []).append(episode)
        return groups

    def _extract_facts_from_episodes(self, episodes: List[Episode], topic: str) -> List[Dict[str, Any]]:
        """Extract candidate semantic facts from a group of episodes, tagging each as
        a contradiction, an update to an existing fact, or a brand-new fact."""
        facts = []
        seen_statements = set()

        for episode in episodes:
            fact_texts = list(episode.extracted_facts)

            # Fall back to the episode summary if nothing was pre-extracted
            if not fact_texts and episode.summary:
                if any(kw in episode.summary.lower() for kw in ('is', 'are', 'was', 'were', 'has', 'have')):
                    fact_texts = [episode.summary]

            for fact_text in fact_texts:
                fact_text = fact_text.strip()
                if len(fact_text) < 10 or fact_text in seen_statements:
                    continue
                seen_statements.add(fact_text)

                contradiction = self._check_contradiction_with_existing(fact_text)
                if contradiction:
                    facts.append({
                        'type': 'contradiction',
                        'statement': fact_text,
                        'confidence': episode.importance_score,
                        'source_episode': episode.episode_id,
                        'contradicts': contradiction,
                        'category': topic,
                    })
                    continue

                existing = self._find_similar_fact(fact_text)
                if existing:
                    facts.append({
                        'type': 'update',
                        'fact_id': existing.fact_id,
                        'statement': fact_text,
                        'confidence': episode.importance_score,
                        'source_episode': episode.episode_id,
                        'existing_fact': existing,
                    })
                else:
                    facts.append({
                        'type': 'new',
                        'statement': fact_text,
                        'confidence': episode.importance_score,
                        'source_episode': episode.episode_id,
                        'category': topic,
                    })

        return facts

    def _check_contradiction_with_existing(self, statement: str) -> Optional[Dict[str, Any]]:
        """Check if a statement contradicts any currently active fact."""
        for fact in self.semantic_memory.get_active_facts():
            if same_topic(statement, fact.statement) and are_contradictory(statement, fact.statement):
                return {
                    'fact_id': fact.fact_id,
                    'statement': fact.statement,
                    'confidence': fact.confidence,
                }
        return None

    def _find_similar_fact(self, statement: str) -> Optional[Fact]:
        """Find an existing fact whose wording is close enough to count as the same fact."""
        words = set(statement.lower().split())
        if not words:
            return None

        for fact in self.semantic_memory.get_active_facts():
            fact_words = set(fact.statement.lower().split())
            overlap = len(words & fact_words) / len(words | fact_words)
            if overlap > self.similarity_threshold:
                return fact
        return None

    # ===== Processing =====

    def _process_fact(self, fact_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create, update, or skip a fact based on its extraction type."""
        fact_type = fact_info['type']

        if fact_type == 'contradiction':
            return self._process_contradiction(fact_info)
        if fact_type == 'update':
            return self._process_update(fact_info)
        if fact_type == 'new':
            return self._process_new(fact_info)
        return {'status': 'error', 'reason': 'unknown_type'}

    def _process_contradiction(self, fact_info: Dict[str, Any]) -> Dict[str, Any]:
        contradiction = fact_info['contradicts']

        resolution = {
            'resolved_fact_id': None,
            'explanation': (
                f"Contradiction found: '{fact_info['statement']}' contradicts "
                f"existing fact '{contradiction['statement']}'"
            ),
            'timestamp': datetime.now().isoformat(),
        }
        self.semantic_memory.record_contradiction(
            fact_ids=[contradiction['fact_id']],
            resolution=resolution,
        )

        if fact_info['confidence'] > contradiction['confidence']:
            updated = self.semantic_memory.update_fact(
                fact_id=contradiction['fact_id'],
                new_statement=fact_info['statement'],
                confidence=fact_info['confidence'],
            )
            if updated:
                updated.source_episodes.append(fact_info['source_episode'])
                return {'status': 'updated', 'fact': updated, 'contradiction_resolved': True}

        # New statement didn't win: keep the existing fact, flag the contradiction
        return {
            'status': 'skipped',
            'reason': 'contradiction_resolved',
            'contradiction': contradiction,
        }

    def _process_update(self, fact_info: Dict[str, Any]) -> Dict[str, Any]:
        existing = fact_info['existing_fact']
        if fact_info['confidence'] > existing.confidence:
            updated = self.semantic_memory.update_fact(
                fact_id=fact_info['fact_id'],
                new_statement=fact_info['statement'],
                confidence=fact_info['confidence'],
            )
            if updated:
                updated.source_episodes.append(fact_info['source_episode'])
                return {'status': 'updated', 'fact': updated}
        return {'status': 'skipped', 'reason': 'lower_confidence'}

    def _process_new(self, fact_info: Dict[str, Any]) -> Dict[str, Any]:
        fact = Fact(
            statement=fact_info['statement'],
            confidence=fact_info['confidence'],
            source_episodes=[fact_info['source_episode']],
            category=fact_info.get('category', 'general'),
            tags={fact_info.get('category', 'general')},
        )

        if fact.confidence < 0.3:
            fact.expires_at = datetime.now() + timedelta(days=7)
        elif fact.confidence < 0.5:
            fact.expires_at = datetime.now() + timedelta(days=30)
        else:
            fact.expires_at = None

        self.semantic_memory.add_fact(fact)
        return {'status': 'created', 'fact': fact}

    def _resolve_contradiction(self, contradiction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Resolve a contradiction found among existing facts: higher confidence
        (then more sources) wins; a true tie leaves both facts active but flagged."""
        fact1 = self.semantic_memory.get_fact(contradiction['fact1']['fact_id'])
        fact2 = self.semantic_memory.get_fact(contradiction['fact2']['fact_id'])
        if not fact1 or not fact2:
            return None

        if fact1.confidence > fact2.confidence:
            winner, loser = fact1, fact2
        elif fact2.confidence > fact1.confidence:
            winner, loser = fact2, fact1
        elif len(fact1.source_episodes) > len(fact2.source_episodes):
            winner, loser = fact1, fact2
        elif len(fact2.source_episodes) > len(fact1.source_episodes):
            winner, loser = fact2, fact1
        else:
            winner, loser = None, None

        if winner and loser:
            resolution = {
                'resolved_fact_id': winner.fact_id,
                'explanation': (
                    f"Fact '{winner.statement}' wins over '{loser.statement}' "
                    f"due to higher confidence ({winner.confidence} > {loser.confidence})"
                ),
                'timestamp': datetime.now().isoformat(),
            }
            self.semantic_memory.record_contradiction(
                fact_ids=[fact1.fact_id, fact2.fact_id], resolution=resolution,
            )
            self.semantic_memory.expire_fact(loser.fact_id)
            return {'winner': winner.fact_id, 'loser': loser.fact_id, 'resolution': resolution}

        # True tie: keep both, but record that they conflict
        resolution = {
            'resolved_fact_id': None,
            'explanation': f"Tie between '{fact1.statement}' and '{fact2.statement}'. Both retained.",
            'timestamp': datetime.now().isoformat(),
            'tie': True,
        }
        self.semantic_memory.record_contradiction(
            fact_ids=[fact1.fact_id, fact2.fact_id], resolution=resolution,
        )
        return {'tie': True, 'fact1': fact1.fact_id, 'fact2': fact2.fact_id, 'resolution': resolution}

    # ===== Introspection =====

    def get_history(self) -> List[Dict[str, Any]]:
        return self._run_history

    def get_statistics(self) -> Dict[str, Any]:
        total_facts = self.semantic_memory.count()
        active_facts = self.semantic_memory.count_active()
        return {
            'total_facts': total_facts,
            'active_facts': active_facts,
            'inactive_facts': total_facts - active_facts,
            'total_runs': len(self._run_history),
            'last_run': self._last_run.isoformat() if self._last_run else None,
            'contradictions': len(self.semantic_memory.get_contradictions()),
        }

    def force_consolidation(self, episode_ids: List[str]) -> Dict[str, Any]:
        """Force consolidation for specific episodes."""
        episodes = [self.episodic_memory.get_episode(eid) for eid in episode_ids]
        episodes = [e for e in episodes if e]

        if not episodes:
            return {'status': 'no_episodes_found', 'episodes_requested': len(episode_ids)}

        return self.run_consolidation(since=datetime.min, force_full=True)