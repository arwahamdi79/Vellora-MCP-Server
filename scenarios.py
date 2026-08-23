# context_eval/scenarios.py
"""
Synthetic long-conversation generator for benchmarking context-management
strategies.

Modeled on a realistic Vellora agent session: routine tool chatter with a
couple of safety-critical facts buried in it. A good context strategy should
still surface those facts even after heavy pruning; that's the thing we
actually measure in benchmark.py, not just raw compression ratio.
"""

import random
from typing import List, Tuple

from memory.short_term_memory import Message


# Facts that MUST still be inferable from the kept context near the end of
# the conversation - these are the "did we lose something important" probes.
KEY_FACTS = [
    "Batch 1042 failed QA due to contamination detected in Line 3.",
    "Recall initiated for Batch 1042 - do not distribute.",
]

FILLER_TOOL_OUTPUTS = [
    "get_medicines() -> 128 medicines returned.",
    "get_batches() -> 340 batches returned, sorted by BatchID descending.",
    "Employee 204 (Jane Cole, QA Staff) is Active.",
    "Production order #881 created for Medicine 12, Supplier 4, Qty 5000.",
    "Batch 998 status changed to 'In Production'.",
    "Quality test recorded for Batch 998: Pass. No remarks.",
    "get_quality_tests() -> 512 records returned.",
    "Supplier 7 delivery confirmed, 3 days ahead of schedule.",
]

FILLER_USER_TURNS = [
    "Can you show me all medicines from Supplier 4?",
    "What's the status of batch 998?",
    "List the last five quality tests.",
    "Who is responsible for production order 881?",
    "Any pending QA batches this week?",
]

FILLER_ASSISTANT_TURNS = [
    "Here are the results you asked for.",
    "I've pulled the latest batch records for you.",
    "That production order is currently in progress.",
    "No pending QA issues found in that range.",
]


def build_conversation(n_messages: int, seed: int = 42) -> List[Message]:
    """
    Build a synthetic conversation of `n_messages` messages. Message 3 (early)
    and one message roughly 80% of the way through carry the two KEY_FACTS,
    so a strategy that prunes only from the middle/oldest end still has to
    reckon with them.
    """
    rng = random.Random(seed)
    messages: List[Message] = []

    key_fact_positions = {
        3: KEY_FACTS[0],
        max(4, int(n_messages * 0.8)): KEY_FACTS[1],
    }

    for i in range(n_messages):
        if i in key_fact_positions:
            role = 'tool' if i % 2 == 0 else 'user'
            content = key_fact_positions[i]
        else:
            roll = rng.random()
            if roll < 0.35:
                role, content = 'user', rng.choice(FILLER_USER_TURNS)
            elif roll < 0.65:
                role, content = 'assistant', rng.choice(FILLER_ASSISTANT_TURNS)
            else:
                role, content = 'tool', rng.choice(FILLER_TOOL_OUTPUTS)
                # Occasionally simulate a large tool payload
                if rng.random() < 0.15:
                    content = content + " " + " ".join(
                        f"[row_{j}: id={rng.randint(1,9999)}]" for j in range(40)
                    )

        messages.append(Message(role=role, content=content))

    return messages


from memory.contradiction import meaningful_words


def key_fact_survival(kept_texts: List[str], min_word_overlap: float = 0.6) -> Tuple[int, int]:
    """
    Return (facts_found, total_facts). A fact counts as "found" if at least
    `min_word_overlap` of its meaningful (non-stopword) words appear anywhere
    in the kept content - not an exact substring match. This means a
    paraphrase like "Batch 1042 failed QA because of contamination" still
    counts as retaining "Batch 1042 failed QA due to contamination detected
    in Line 3", since the substance survived even though the wording changed.
    """
    kept_words = set(" ".join(kept_texts).lower().split())
    found = 0
    for fact in KEY_FACTS:
        fact_words = meaningful_words(fact)
        if not fact_words:
            continue
        overlap = len(fact_words & kept_words) / len(fact_words)
        if overlap >= min_word_overlap:
            found += 1
    return found, len(KEY_FACTS)