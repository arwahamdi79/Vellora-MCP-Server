# memory/contradiction.py
"""
Shared contradiction-detection utilities.

Previously this logic was copy-pasted (with drifting behavior) into both
consolidation.py and semantic_memory.py. It now lives in one place so both
callers agree on what "same topic" and "contradictory" mean.
"""

from typing import Set

STOPWORDS: Set[str] = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'for', 'of',
    'and', 'or', 'but', 'in', 'on', 'at', 'with', 'without', 'by',
    'from', 'up', 'about', 'into', 'through', 'during', 'including',
    'my', 'your', 'his', 'her', 'its', 'our', 'their', 'me', 'you',
    'him', 'us', 'them',
}

NEGATIONS: Set[str] = {
    'not', 'never', 'no', 'cannot', "can't", 'without', 'except', 'unless', 'none',
}

OPPOSING_PAIRS = [
    ('true', 'false'), ('yes', 'no'), ('good', 'bad'), ('high', 'low'),
    ('large', 'small'), ('big', 'small'), ('fast', 'slow'), ('hot', 'cold'),
    ('old', 'new'), ('early', 'late'), ('can', 'cannot'), ('will', 'will not'),
    ('should', 'should not'), ('must', 'must not'), ('allowed', 'forbidden'),
    ('permitted', 'prohibited'), ('available', 'unavailable'), ('present', 'absent'),
    ('include', 'exclude'), ('contains', 'does not contain'), ('has', 'does not have'),
    ('like', 'dislike'), ('love', 'hate'), ('agree', 'disagree'), ('approve', 'disapprove'),
    ('accept', 'reject'), ('success', 'failure'), ('win', 'lose'), ('right', 'wrong'),
    ('correct', 'incorrect'), ('possible', 'impossible'), ('likely', 'unlikely'),
    ('certain', 'uncertain'), ('always', 'never'), ('ever', 'never'),
    ('all', 'none'), ('every', 'no'), ('some', 'none'), ('on', 'off'),
    ('open', 'closed'), ('start', 'stop'), ('begin', 'end'), ('first', 'last'),
    ('min', 'max'), ('minimum', 'maximum'), ('least', 'most'),
]

CONTRADICTION_PREFIXES = [
    'anti', 'counter', 'de', 'dis', 'il', 'im', 'in', 'ir', 'mal', 'mis', 'non', 'un',
]


def meaningful_words(statement: str) -> Set[str]:
    """Lowercase, split, and drop stopwords/short tokens."""
    return {
        w for w in statement.lower().split()
        if len(w) > 2 and w not in STOPWORDS
    }


def same_topic(stmt1: str, stmt2: str, min_common: int = 2) -> bool:
    """Two statements are 'about the same thing' if they share enough meaningful words."""
    common = meaningful_words(stmt1) & meaningful_words(stmt2)
    return len(common) >= min_common


def are_contradictory(stmt1: str, stmt2: str) -> bool:
    """
    Heuristic contradiction check. Assumes the caller has already confirmed
    the two statements are on the same topic (see same_topic).

    Checks, in order:
      1. One statement is negated and the other isn't.
      2. The statements contain an opposing word pair (good/bad, can/cannot, ...).
      3. One statement's word is a negated-prefix form of a word in the other
         (e.g. "possible" / "impossible").
    """
    stmt1_lower, stmt2_lower = stmt1.lower(), stmt2.lower()
    words1, words2 = set(stmt1_lower.split()), set(stmt2_lower.split())

    has_neg1 = any(neg in words1 for neg in NEGATIONS)
    has_neg2 = any(neg in words2 for neg in NEGATIONS)
    if has_neg1 != has_neg2:
        return True

    for word1, word2 in OPPOSING_PAIRS:
        if (word1 in stmt1_lower and word2 in stmt2_lower) or \
           (word2 in stmt1_lower and word1 in stmt2_lower):
            return True

    for prefix in CONTRADICTION_PREFIXES:
        for word in words1:
            if word.startswith(prefix) and word[len(prefix):] in words2:
                return True
        for word in words2:
            if word.startswith(prefix) and word[len(prefix):] in words1:
                return True

    return False