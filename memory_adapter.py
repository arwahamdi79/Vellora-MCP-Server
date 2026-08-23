# agent/memory_adapter.py
"""
Replaces mcp_server's old `memory.episodic_memory.maybe_remember` /
`load_memory_context` functions with Member 1's MemoryManager package.

Migration: in mcp_server/tools.py, change

    from .memory.episodic_memory import (
        maybe_remember,
        load_memory_context,
    )

to

    from agent.memory_adapter import maybe_remember, load_memory_context

Call sites in tools.py are unchanged - this module matches their exact
signatures (`maybe_remember(turn_text=..., entity_id=...)` and
`load_memory_context(entity_id=..., opening_message=...)`), it just routes
through MemoryManager's episodic/semantic layers instead of writing memory
directly (see maybe_remember's docstring for why it writes straight to
episodic memory rather than going through the promote/drop router).

One MemoryManager per entity_id (e.g. "batch_1042"), so each batch/entity
gets its own episodic/semantic history rather than one global pool. This
mirrors the original module's per-entity_id scoping.
"""

from typing import Any, Dict, List, Optional

from memory.memory_manager import MemoryManager
from memory.episodic_memory import Episode


_managers: Dict[str, MemoryManager] = {}


def _get_manager(entity_id: str) -> MemoryManager:
    """Get or create the MemoryManager for a given entity (e.g. a batch)."""
    manager = _managers.get(entity_id)
    if manager is None:
        manager = MemoryManager()
        manager.start_session(session_id=f"session_{entity_id}", user_id=entity_id)
        _managers[entity_id] = manager
    return manager


def maybe_remember(turn_text: str, entity_id: str) -> Dict[str, Any]:
    """
    Record a significant event for an entity (called from tools.py after
    change_batch_status / add_quality_test).

    This bypasses PromoteDropRouter deliberately: by the time an MCP tool
    calls this function, the caller has already decided the event is worth
    remembering - a real batch status change or QA result - so re-scoring it
    through the generic organic-chat importance heuristic is the wrong tool.
    It would also silently drop most of these events in practice: that
    heuristic gives role-based bonuses to 'user'/'tool'/'assistant' messages
    but not 'system', so these events would usually land under the default
    0.6 promotion threshold and never reach episodic memory at all. So we
    write directly to episodic memory instead, and kick off consolidation
    if it hasn't run yet, so the event is available as a semantic fact as
    soon as possible rather than waiting on the usual interval.
    """
    manager = _get_manager(entity_id)
    cleaned = turn_text.strip()

    episode = Episode(
        summary=cleaned.replace('\n', ' ')[:200],
        details={'entity_id': entity_id, 'full_text': cleaned},
        importance_score=0.75,
        tags={entity_id},
        extracted_facts=[cleaned.replace('\n', '. ')],
        context={'source': 'tool_event'},
        session_id=manager._session_id,
        user_id=manager._user_id,
    )
    manager.episodic.add_episode(episode)
    manager._check_consolidation()  # runs immediately on the first event, per the usual interval logic after that

    return {'stored': True, 'entity_id': entity_id, 'episode_id': episode.episode_id}


def load_memory_context(entity_id: str, opening_message: str = "",
                         strategy: str = 'zone_based_pruning', **strategy_kwargs) -> Dict[str, Any]:
    """
    Build a memory context for an entity (called from tools.py's
    get_batch_memory tool). Returns both the formatted prompt context and,
    if `opening_message` is given, the specific facts/episodes it matched -
    useful for a tool result the LLM can read directly rather than having to
    parse the full formatted context block.
    """
    manager = _get_manager(entity_id)
    context = manager.get_context(strategy=strategy, **strategy_kwargs)

    related_facts: List[str] = []
    related_episodes: List[str] = []
    if opening_message:
        search_results = manager.search_memory(opening_message)
        related_facts = [f['statement'] for f in search_results['semantic']]
        related_episodes = [e['summary'] for e in search_results['episodic']]

    return {
        'entity_id': entity_id,
        'context': context,
        'related_facts': related_facts,
        'related_episodes': related_episodes,
    }


def get_manager(entity_id: str) -> Optional[MemoryManager]:
    """Expose the underlying MemoryManager for an entity, e.g. for
    agent.py to run consolidation or pull statistics. Returns None if no
    manager has been created for that entity yet (i.e. nothing recorded)."""
    return _managers.get(entity_id)


def reset_all():
    """Test/demo helper: clear all per-entity managers."""
    _managers.clear()