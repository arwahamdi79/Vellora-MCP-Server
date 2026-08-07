# memory/semantic_memory.py
"""
Semantic memory for storing distilled facts with versioning and expiration.
Facts are only written through consolidation.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from .contradiction import same_topic, are_contradictory


@dataclass
class Fact:
    """A single semantic fact with versioning and expiration."""

    fact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    statement: str = ""
    source_episodes: List[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    version: int = 1
    previous_version_id: Optional[str] = None  # For rollback/audit
    tags: Set[str] = field(default_factory=set)
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    contradiction_resolved: bool = False
    resolved_contradiction_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'fact_id': self.fact_id,
            'statement': self.statement,
            'source_episodes': self.source_episodes,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'version': self.version,
            'previous_version_id': self.previous_version_id,
            'tags': list(self.tags),
            'category': self.category,
            'metadata': self.metadata,
            'is_active': self.is_active,
            'contradiction_resolved': self.contradiction_resolved,
            'resolved_contradiction_id': self.resolved_contradiction_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Fact':
        return cls(
            fact_id=data.get('fact_id', str(uuid.uuid4())),
            statement=data.get('statement', ''),
            source_episodes=data.get('source_episodes', []),
            confidence=data.get('confidence', 0.5),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if 'updated_at' in data else datetime.now(),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
            version=data.get('version', 1),
            previous_version_id=data.get('previous_version_id'),
            tags=set(data.get('tags', [])),
            category=data.get('category', 'general'),
            metadata=data.get('metadata', {}),
            is_active=data.get('is_active', True),
            contradiction_resolved=data.get('contradiction_resolved', False),
            resolved_contradiction_id=data.get('resolved_contradiction_id'),
        )

    def update(self, new_statement: str, confidence: Optional[float] = None,
               expires_at: Optional[datetime] = None, **kwargs) -> 'Fact':
        """Update the fact in place (bumps version) and return a snapshot of the old version."""
        old_version = self.version
        old_statement = self.statement

        old_fact = Fact(
            fact_id=f"{self.fact_id}_v{old_version}",
            statement=old_statement,
            source_episodes=self.source_episodes.copy(),
            confidence=self.confidence,
            created_at=self.created_at,
            updated_at=datetime.now(),
            expires_at=self.expires_at,
            version=old_version,
            previous_version_id=self.previous_version_id,
            tags=self.tags.copy(),
            category=self.category,
            metadata=self.metadata.copy(),
            is_active=False,
        )

        self.statement = new_statement
        self.version += 1
        self.updated_at = datetime.now()
        self.previous_version_id = self.fact_id

        if confidence is not None:
            self.confidence = confidence
        if expires_at is not None:
            self.expires_at = expires_at

        for key, value in kwargs.items():
            if hasattr(self, key) and key not in ('fact_id', 'version', 'previous_version_id'):
                setattr(self, key, value)

        return old_fact

    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now() > self.expires_at

    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired()


class SemanticMemory:
    """
    Stores semantic facts with versioning and expiration.
    Built exclusively through consolidation.
    """

    def __init__(self):
        self._facts: Dict[str, Fact] = {}
        self._by_category: Dict[str, Set[str]] = {}
        self._by_tag: Dict[str, Set[str]] = {}
        self._version_history: Dict[str, List[Fact]] = {}  # original_id -> list of versions
        self._contradictions: Dict[str, Dict[str, Any]] = {}  # contradiction_id -> {fact_ids, resolution}

    def add_fact(self, fact: Fact) -> str:
        """Add a new fact (only called by consolidation)."""
        self._facts[fact.fact_id] = fact
        self._by_category.setdefault(fact.category, set()).add(fact.fact_id)
        for tag in fact.tags:
            self._by_tag.setdefault(tag, set()).add(fact.fact_id)
        if fact.previous_version_id:
            self._version_history.setdefault(fact.previous_version_id, []).append(fact)
        return fact.fact_id

    def get_fact(self, fact_id: str) -> Optional[Fact]:
        return self._facts.get(fact_id)

    def get_active_facts(self) -> List[Fact]:
        return [f for f in self._facts.values() if f.is_valid()]

    def get_facts_by_category(self, category: str) -> List[Fact]:
        fact_ids = self._by_category.get(category, set())
        return [self._facts[fid] for fid in fact_ids if fid in self._facts and self._facts[fid].is_valid()]

    def get_facts_by_tag(self, tag: str) -> List[Fact]:
        fact_ids = self._by_tag.get(tag, set())
        return [self._facts[fid] for fid in fact_ids if fid in self._facts and self._facts[fid].is_valid()]

    def get_fact_history(self, fact_id: str) -> List[Fact]:
        history = list(self._version_history.get(fact_id, []))
        current = self._facts.get(fact_id)
        if current and current.is_active:
            history.append(current)
        return sorted(history, key=lambda f: f.version)

    def search_facts(self, query: str, n: int = 5) -> List[Fact]:
        """
        Score facts by how many query words they contain, with a bonus for
        containing the query as an exact phrase. Word-overlap scoring (rather
        than requiring the whole query as a literal substring) means a query
        like "cats fly" still matches a fact statement like "Cats cannot fly".
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        if not query_words:
            return []

        scored = []
        for fact in self._facts.values():
            if not fact.is_valid():
                continue

            statement_lower = fact.statement.lower()
            score = len(query_words & set(statement_lower.split()))
            if query_lower in statement_lower:
                score += 2
            if any(query_lower in tag.lower() for tag in fact.tags):
                score += 1

            if score > 0:
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:n]]

    def update_fact(self, fact_id: str, new_statement: str,
                     confidence: Optional[float] = None) -> Optional[Fact]:
        """Update a fact in place (bumps its version) and archive the prior version."""
        fact = self._facts.get(fact_id)
        if not fact or not fact.is_valid():
            return None

        old_version = fact.update(new_statement, confidence)
        self._version_history.setdefault(fact_id, []).append(old_version)
        return fact

    def expire_fact(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if not fact:
            return False
        fact.is_active = False
        fact.expires_at = datetime.now()
        fact.updated_at = datetime.now()
        return True

    def record_contradiction(self, fact_ids: List[str], resolution: Dict[str, Any]) -> str:
        """
        Record how a contradiction was resolved.

        resolution: {
            'resolved_fact_id': '...',  # the fact that wins, or None for a tie
            'explanation': '...',
            'timestamp': '...'
        }
        """
        contradiction_id = str(uuid.uuid4())
        self._contradictions[contradiction_id] = {
            'fact_ids': fact_ids,
            'resolution': resolution,
            'timestamp': datetime.now().isoformat(),
            'resolved': True,
        }
        for fid in fact_ids:
            fact = self._facts.get(fid)
            if fact:
                fact.contradiction_resolved = True
                fact.resolved_contradiction_id = contradiction_id
        return contradiction_id

    def get_contradictions(self) -> List[Dict[str, Any]]:
        return [{'id': cid, **data} for cid, data in self._contradictions.items()]

    def find_contradictions(self) -> List[Dict[str, Any]]:
        """Find potential contradictions among all active facts (pairwise scan)."""
        active_facts = self.get_active_facts()
        contradictions = []

        for i in range(len(active_facts)):
            for j in range(i + 1, len(active_facts)):
                fact1, fact2 = active_facts[i], active_facts[j]
                if same_topic(fact1.statement, fact2.statement) and \
                   are_contradictory(fact1.statement, fact2.statement):
                    contradictions.append({
                        'fact1': fact1.to_dict(),
                        'fact2': fact2.to_dict(),
                        'category': fact1.category,
                        'severity': 'high' if fact1.confidence > 0.7 and fact2.confidence > 0.7 else 'medium',
                    })

        return contradictions

    def count(self) -> int:
        return len(self._facts)

    def count_active(self) -> int:
        return len(self.get_active_facts())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'facts': {fid: f.to_dict() for fid, f in self._facts.items()},
            'count': len(self._facts),
            'active_count': self.count_active(),
            'contradictions': self.get_contradictions(),
        }