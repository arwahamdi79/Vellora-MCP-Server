# memory/__init__.py
"""
Memory system for an MCP agent: short-term, episodic, and semantic memory,
with promotion/drop routing and periodic consolidation.
"""

from .short_term_memory import ShortTermMemory, Scratchpad, Message
from .episodic_memory import EpisodicMemory, Episode
from .semantic_memory import SemanticMemory, Fact
from .promote_drop_router import PromoteDropRouter, RoutingDecision
from .consolidation import ConsolidationLayer
from .memory_manager import MemoryManager

__all__ = [
    'ShortTermMemory',
    'Scratchpad',
    'Message',
    'EpisodicMemory',
    'Episode',
    'SemanticMemory',
    'Fact',
    'PromoteDropRouter',
    'RoutingDecision',
    'ConsolidationLayer',
    'MemoryManager',
]