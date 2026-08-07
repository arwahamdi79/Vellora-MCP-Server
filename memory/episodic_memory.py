# memory/episodic_memory.py
"""
Episodic memory for storing significant experiences.
Each episode is a structured record of a meaningful interaction.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid


@dataclass
class Episode:
    """A single episode/experience stored in episodic memory."""

    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    importance_score: float = 0.5  # 0-1 scale
    tags: Set[str] = field(default_factory=set)
    related_episodes: List[str] = field(default_factory=list)  # episode_ids
    extracted_facts: List[str] = field(default_factory=list)  # candidate facts for consolidation
    context: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    user_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode_id': self.episode_id,
            'summary': self.summary,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'importance_score': self.importance_score,
            'tags': list(self.tags),
            'related_episodes': self.related_episodes,
            'extracted_facts': self.extracted_facts,
            'context': self.context,
            'session_id': self.session_id,
            'user_id': self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Episode':
        return cls(
            episode_id=data.get('episode_id', str(uuid.uuid4())),
            summary=data.get('summary', ''),
            details=data.get('details', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            importance_score=data.get('importance_score', 0.5),
            tags=set(data.get('tags', [])),
            related_episodes=data.get('related_episodes', []),
            extracted_facts=data.get('extracted_facts', []),
            context=data.get('context', {}),
            session_id=data.get('session_id', ''),
            user_id=data.get('user_id', ''),
        )


class EpisodicMemory:
    """Stores significant episodes/experiences with retrieval and management."""

    def __init__(self, storage_path: Optional[str] = None):
        self._episodes: Dict[str, Episode] = {}
        self._by_session: Dict[str, List[str]] = {}
        self._by_user: Dict[str, List[str]] = {}
        self._by_tag: Dict[str, Set[str]] = {}
        self._storage_path = storage_path

    def add_episode(self, episode: Episode) -> str:
        """Add an episode to memory."""
        self._episodes[episode.episode_id] = episode

        if episode.session_id:
            self._by_session.setdefault(episode.session_id, []).append(episode.episode_id)
        if episode.user_id:
            self._by_user.setdefault(episode.user_id, []).append(episode.episode_id)
        for tag in episode.tags:
            self._by_tag.setdefault(tag, set()).add(episode.episode_id)

        return episode.episode_id

    def get_episode(self, episode_id: str) -> Optional[Episode]:
        return self._episodes.get(episode_id)

    def get_recent_episodes(self, n: int = 10, user_id: Optional[str] = None) -> List[Episode]:
        episodes = list(self._episodes.values())
        if user_id:
            episodes = [e for e in episodes if e.user_id == user_id]
        episodes.sort(key=lambda e: e.timestamp, reverse=True)
        return episodes[:n]

    def get_episodes_by_session(self, session_id: str) -> List[Episode]:
        episode_ids = self._by_session.get(session_id, [])
        return [self._episodes[eid] for eid in episode_ids if eid in self._episodes]

    def get_episodes_by_tag(self, tag: str) -> List[Episode]:
        episode_ids = self._by_tag.get(tag, set())
        return [self._episodes[eid] for eid in episode_ids if eid in self._episodes]

    def get_episodes_by_importance(self, min_score: float = 0.5) -> List[Episode]:
        return [e for e in self._episodes.values() if e.importance_score >= min_score]

    def search_episodes(self, query: str, n: int = 5) -> List[Episode]:
        """
        Score episodes by word overlap between the query and the summary/details,
        with a bonus for an exact phrase match. Word-overlap (rather than one
        literal substring match) means "cats fly" still matches a summary like
        "...I think cats can fly...".
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        if not query_words:
            return []

        scored = []
        for episode in self._episodes.values():
            summary_lower = episode.summary.lower()
            details_lower = json.dumps(episode.details).lower()

            score = len(query_words & set(summary_lower.split()))
            if query_lower in summary_lower:
                score += 2
            if query_lower in details_lower:
                score += 1
            if any(query_lower in tag.lower() for tag in episode.tags):
                score += 0.5

            if score > 0:
                scored.append((score, episode))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:n]]

    def update_episode(self, episode_id: str, **kwargs) -> bool:
        episode = self._episodes.get(episode_id)
        if not episode:
            return False

        for key, value in kwargs.items():
            if not hasattr(episode, key) or key == 'episode_id':
                continue
            if key == 'tags':
                for tag in episode.tags:
                    self._by_tag.get(tag, set()).discard(episode_id)
                episode.tags = set(value)
                for tag in episode.tags:
                    self._by_tag.setdefault(tag, set()).add(episode_id)
            else:
                setattr(episode, key, value)

        return True

    def delete_episode(self, episode_id: str) -> bool:
        episode = self._episodes.pop(episode_id, None)
        if not episode:
            return False

        if episode.session_id in self._by_session:
            self._by_session[episode.session_id].remove(episode_id)
        if episode.user_id in self._by_user:
            self._by_user[episode.user_id].remove(episode_id)
        for tag in episode.tags:
            self._by_tag.get(tag, set()).discard(episode_id)

        return True

    def get_episodes_for_consolidation(self,
                                        since: Optional[datetime] = None,
                                        min_importance: float = 0.3) -> List[Episode]:
        """Get episodes ready for semantic consolidation, oldest first."""
        episodes = list(self._episodes.values())
        if since:
            episodes = [e for e in episodes if e.timestamp >= since]
        episodes = [e for e in episodes if e.importance_score >= min_importance]
        episodes.sort(key=lambda e: e.timestamp)
        return episodes

    def count(self) -> int:
        return len(self._episodes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'episodes': {eid: e.to_dict() for eid, e in self._episodes.items()},
            'count': len(self._episodes),
            'by_session': {s: list(ids) for s, ids in self._by_session.items()},
            'by_tag': {t: list(ids) for t, ids in self._by_tag.items()},
        }

    def save_to_file(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def load_from_file(self, path: str):
        with open(path, 'r') as f:
            data = json.load(f)

        for episode_id, episode_data in data.get('episodes', {}).items():
            episode = Episode.from_dict(episode_data)
            self._episodes[episode_id] = episode

            if episode.session_id:
                self._by_session.setdefault(episode.session_id, []).append(episode_id)
            if episode.user_id:
                self._by_user.setdefault(episode.user_id, []).append(episode_id)
            for tag in episode.tags:
                self._by_tag.setdefault(tag, set()).add(episode_id)