# memory/short_term_memory.py
"""
Short-term memory with rolling buffer and scratchpad.
Implements context window management strategies.
"""

from typing import List, Dict, Any, Optional, Deque
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import json
import hashlib


@dataclass
class Message:
    """Single message in the short-term memory."""
    role: str  # 'user', 'assistant', 'tool', 'system'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'message_id': self.message_id,
        }


@dataclass
class Scratchpad:
    """
    Working memory for the agent's current plan, sub-goals, and state.
    Survives transcript pruning.
    """
    plan: str = ""
    sub_goal: str = ""
    working_state: Dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    total_steps: int = 0
    notes: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = datetime.now()

    def add_note(self, note: str):
        self.notes.append(f"[{datetime.now().isoformat()}] {note}")
        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan': self.plan,
            'sub_goal': self.sub_goal,
            'working_state': self.working_state,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'notes': self.notes[-10:],
            'last_updated': self.last_updated.isoformat(),
        }

    def to_prompt(self) -> str:
        """Format scratchpad for inclusion in prompts."""
        lines = ["=== AGENT SCRATCHPAD ==="]
        if self.plan:
            lines.append(f"Plan: {self.plan}")
        if self.sub_goal:
            lines.append(f"Current Sub-Goal: {self.sub_goal}")
        if self.working_state:
            lines.append(f"Working State: {json.dumps(self.working_state, indent=2)}")
        if self.current_step > 0:
            lines.append(f"Progress: Step {self.current_step} of {self.total_steps}")
        if self.notes:
            lines.append(f"Recent Notes: {self.notes[-3:]}")
        return "\n".join(lines)


class ShortTermMemory:
    """Rolling message buffer for the agent's short-term memory."""

    def __init__(self, max_size: int = 100):
        self.messages: Deque[Message] = deque(maxlen=max_size)
        self.scratchpad = Scratchpad()
        self.max_size = max_size
        self._strategy_metadata: Dict[str, Any] = {}

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        msg = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(msg)
        return msg

    def get_messages(self) -> List[Message]:
        return list(self.messages)

    def get_messages_dict(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self.messages]

    def get_recent(self, n: int) -> List[Message]:
        return list(self.messages)[-n:]

    def clear(self):
        self.messages.clear()

    # ===== Context Management Strategies =====

    def strategy_sliding_window(self, window_size: int = 10) -> List[Message]:
        """Keep only the most recent N messages."""
        return self.get_recent(window_size)

    def strategy_observation_masking(self, keep_tool_outputs: int = 3) -> List[Message]:
        """Keep all messages, but mask all but the most recent K tool outputs."""
        result = []
        tool_output_count = 0

        for msg in reversed(self.messages):
            if msg.role != 'tool':
                result.append(msg)
                continue

            if tool_output_count < keep_tool_outputs:
                result.append(msg)
                tool_output_count += 1
            else:
                result.append(Message(
                    role='tool',
                    content=f"[MASKED] Tool output truncated. {len(msg.content)} tokens omitted.",
                    metadata={'masked': True, 'original_length': len(msg.content)},
                ))

        result.reverse()
        return result

    def strategy_recursive_summarization(self,
                                          max_tokens: int = 4000,
                                          summarizer_func=None) -> List[Dict[str, Any]]:
        """Summarize older messages when exceeding a token budget. `summarizer_func`
        takes text and returns a summary; falls back to truncation if not given."""
        if summarizer_func is None:
            return self._simple_truncate(max_tokens)

        messages = list(self.messages)
        if self._estimate_tokens(messages) <= max_tokens:
            return [m.to_dict() for m in messages]

        # Binary search for the split point that fits recent messages in budget
        lo, hi = 0, len(messages)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._estimate_tokens(messages[mid:]) <= max_tokens * 0.7:  # reserve room for summary
                hi = mid
            else:
                lo = mid + 1

        old_messages = messages[:lo]
        recent_messages = messages[lo:]

        old_text = "\n".join(f"{m.role}: {m.content}" for m in old_messages)
        summary = summarizer_func(old_text)

        result = [{
            'role': 'system',
            'content': f"[SUMMARY] Previous conversation:\n{summary}",
            'metadata': {'summary': True, 'original_count': len(old_messages)},
        }]
        result.extend(m.to_dict() for m in recent_messages)
        return result

    def _simple_truncate(self, max_tokens: int) -> List[Dict[str, Any]]:
        """Fallback for recursive summarization when no summarizer is provided."""
        messages = list(self.messages)
        result = []
        token_count = 0

        for msg in reversed(messages):
            msg_tokens = self._estimate_tokens([msg])
            if token_count + msg_tokens <= max_tokens:
                result.append(msg.to_dict())
                token_count += msg_tokens
            else:
                result.append({
                    'role': msg.role,
                    'content': msg.content[:100] + "... [TRUNCATED]",
                    'metadata': {'truncated': True, **msg.metadata},
                })
                break

        result.reverse()
        return result

    def strategy_zone_based_pruning(self, zones: Optional[Dict[str, int]] = None) -> List[Message]:
        """
        Apply different retention limits per role, e.g.
        {'system': 999, 'user': 5, 'assistant': 5, 'tool': 3} (the default).
        """
        zones = {'system': 999, 'user': 5, 'assistant': 5, 'tool': 3, **(zones or {})}

        by_role: Dict[str, List[Message]] = {}
        for msg in self.messages:
            by_role.setdefault(msg.role, []).append(msg)

        kept = []
        for role, msgs in by_role.items():
            kept.extend(msgs[-zones.get(role, 5):])

        kept.sort(key=lambda m: m.timestamp)
        return kept

    def _estimate_tokens(self, messages: List[Message]) -> int:
        """Rough token estimation (4 chars per token)."""
        return sum(len(msg.content) // 4 for msg in messages)

    # ===== Strategy Runner =====

    def apply_strategy(self, strategy: str, **kwargs) -> List[Message]:
        strategy_map = {
            'sliding_window': self.strategy_sliding_window,
            'observation_masking': self.strategy_observation_masking,
            'recursive_summarization': self.strategy_recursive_summarization,
            'zone_based_pruning': self.strategy_zone_based_pruning,
        }
        if strategy not in strategy_map:
            raise ValueError(f"Unknown strategy: {strategy}")
        return strategy_map[strategy](**kwargs)

    def apply_and_update(self, strategy: str, **kwargs) -> List[Message]:
        """Apply a strategy and replace the message buffer with the kept set."""
        kept = self.apply_strategy(strategy, **kwargs)

        self.messages.clear()
        for msg in kept:
            if isinstance(msg, Message):
                self.messages.append(msg)
            elif isinstance(msg, dict):
                self.messages.append(Message(
                    role=msg['role'],
                    content=msg['content'],
                    metadata=msg.get('metadata', {}),
                ))

        self._strategy_metadata = {
            'strategy': strategy,
            'applied_at': datetime.now().isoformat(),
            'kwargs': kwargs,
            'message_count': len(self.messages),
        }

        return list(self.messages)

    def get_context_for_prompt(self, strategy: str = 'sliding_window', **kwargs) -> str:
        """Get formatted context for the model prompt."""
        messages = self.apply_strategy(strategy, **kwargs)
        context = self.scratchpad.to_prompt() + "\n\n=== CONVERSATION ===\n"

        for msg in messages:
            if isinstance(msg, dict):
                context += f"[{msg['role']}]: {msg['content']}\n"
            else:
                context += f"[{msg.role}]: {msg.content}\n"

        return context

    def to_dict(self) -> Dict[str, Any]:
        return {
            'messages': [m.to_dict() for m in self.messages],
            'scratchpad': self.scratchpad.to_dict(),
            'strategy_metadata': self._strategy_metadata,
            'size': len(self.messages),
            'max_size': self.max_size,
        }