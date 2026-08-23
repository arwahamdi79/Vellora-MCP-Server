# memory — Memory System

Three-tier memory for an agent: a rolling short-term buffer, episodic
memory for significant events, and semantic memory for distilled facts —
plus the machinery that moves information between them.

```
short-term buffer  --(promote/drop router)-->  episodic memory  --(consolidation)-->  semantic memory
   (recent turns)         importance-scored         (raw events)      periodic, batched      (distilled facts,
                                                                                                versioned, contradiction-checked)
```

## Why three tiers

- **Short-term memory** is everything currently in the conversation window.
  Cheap to read/write, but bounded — it can't hold a whole session's history.
- **Episodic memory** holds specific things that happened — "batch 1042
  failed QA" — kept as discrete, timestamped records, not summarized.
- **Semantic memory** holds distilled *facts* — durable statements built
  from episodes, with a confidence score, an expiration policy, and a
  version history. Only written by consolidation, never directly, so facts
  are always traceable back to the episodes that produced them.

## Components

### `short_term_memory.py` — `ShortTermMemory`, `Scratchpad`, `Message`

A `Message` is one turn (`role`, `content`, `timestamp`, `metadata`).
`ShortTermMemory` holds them in a bounded rolling buffer and exposes four
strategies for fitting the buffer into a prompt budget:

| Strategy | What it does | Trade-off |
|---|---|---|
| `sliding_window` | Keep the last N messages | Cheap, purely positional — old facts are just gone |
| `observation_masking` | Keep everything, mask all but the last K tool outputs | Protects reasoning trail, not tool-buried facts |
| `recursive_summarization` | Summarize old messages once the buffer exceeds a token budget (via an injected `summarizer_func`) | Only strategy that's content-aware, but costs a real LLM call |
| `zone_based_pruning` | Different retention limits per role (e.g. keep all `system`, last 5 `user`) | Predictable, but same positional blind spot as sliding window |

See `context_eval/` for a benchmark of all four on a synthetic long
conversation, including how often each one loses a safety-critical fact.

`Scratchpad` is separate working memory (current plan, sub-goal, step
count, notes) that survives short-term pruning — it's not part of the
message buffer, so none of the four strategies above can accidentally
drop it.

### `episodic_memory.py` — `Episode`, `EpisodicMemory`

An `Episode` is a record of something that happened: a summary, full
details, an importance score, tags, and `extracted_facts` — candidate
statements pulled out of its content, which is what consolidation reads
later. `EpisodicMemory` indexes episodes by session, user, and tag, and
supports keyword search (word-overlap scored, not exact-substring — a
search for "cats fly" matches an episode saying "cats can fly").

### `promote_drop_router.py` — `PromoteDropRouter`, `RoutingDecision`

Decides, per item, whether to `promote` it to episodic memory, `defer` it,
or let it be `forgotten`. Importance is scored from content length,
critical keywords, urgency language, goal relevance, novelty, and message
role, then compared against a threshold. Every decision carries its
reasoning as a human-readable string, not just a label — useful for
auditing why something was kept or dropped.

This router is for *organic* conversation turns, where "is this worth
remembering" genuinely needs a heuristic. It is deliberately **not** used
for structured domain events (see `agent/memory_adapter.py`) — those
already carry their own "this matters" signal from the caller, and running
them through this heuristic anyway was an actual bug caught during
integration testing (system-role events scored under the promotion
threshold and were silently dropped).

### `semantic_memory.py` — `Fact`, `SemanticMemory`

A `Fact` is a versioned, confidence-scored statement with an optional
expiration date. Updating a fact bumps its version and archives the old
one rather than overwriting it — nothing is silently lost. `SemanticMemory`
indexes facts by category/tag, supports keyword search, and can scan all
active facts for contradictions (`find_contradictions`).

Contradiction detection (shared with `consolidation.py` via
`contradiction.py`) checks two things: are two statements about the same
topic (enough overlapping meaningful words), and do they actually conflict
(mismatched negation, an opposing word pair like allowed/forbidden, or a
negated-prefix pair like possible/impossible).

### `consolidation.py` — `ConsolidationLayer`

The periodic batch job that turns episodes into facts. Runs on a schedule
("periodic pass... never at write time" is a real design choice, not
laziness — see below), and for each candidate fact:

- if it contradicts an existing fact → the higher-confidence one wins and
  is recorded as the update; a tie keeps both but flags the conflict
- if it closely matches an existing fact → updates that fact if the new
  version has higher confidence, otherwise skips it
- otherwise → creates a new fact, with an expiration date scaled to how
  low its confidence is (low confidence facts expire in a week, unless
  confidence rises above 0.5, in which case they don't expire)

It also does a second pass over all currently-active facts to catch
contradictions that formed across separate consolidation runs, not just
within one.

**Why periodic, not real-time:** a single episode surviving in isolation
tells you nothing about whether it contradicts something recorded five
minutes from now. Batching lets consolidation compare against the full
current set of active facts, and lets facts within the same batch that
turn out to conflict get caught by the follow-up contradiction scan even
if they weren't caught pairwise during extraction. The trade-off is that a
fact you just recorded may not show up in semantic memory until the next
scheduled run — call `MemoryManager.run_consolidation_now()` to force it.

### `memory_manager.py` — `MemoryManager`

The single entry point that ties all of the above together:

```python
from memory import MemoryManager

mm = MemoryManager(short_term_max_size=100, importance_threshold=0.6)
mm.start_session(session_id="s1", user_id="u1")

mm.add_message("user", "Batch 1042 failed contamination testing.")
mm.update_scratchpad(plan="Investigate batch 1042")

context = mm.get_context(strategy="zone_based_pruning")   # ready to hand to an LLM
results = mm.search_memory("batch 1042")                   # across all three tiers
mm.run_consolidation_now()                                  # force episodic -> semantic

mm.end_session()  # flushes remaining short-term messages, runs a final consolidation pass
```

`add_message` routes the short-term buffer through the promote/drop router
when it's about to overflow — *before* appending the new message, so the
buffer's own size cap can't silently evict something before the router
sees it. `get_context` assembles semantic facts + recent episodes +
short-term buffer (under whichever of the four strategies you choose) into
one prompt-ready string.

## Running the tests

```bash
python -m memory.quick_test
```

Seven tests, each exercising a real end-to-end path rather than a mocked
one: contradiction detection, contradiction resolution during
consolidation, duplicate detection in the router, short-term buffer
overflow, scratchpad state, router promote/forget reasoning (printed, not
just asserted), and the full pipeline from message → promotion →
consolidation → searchable semantic fact.

## Design notes worth knowing

- **Contradiction and duplicate detection are both heuristic**, not
  semantic — they work on word overlap and a fixed list of opposing word
  pairs / negation markers. They catch clean cases ("cats can fly" vs.
  "cats cannot fly") and will miss subtler ones. Good enough to demonstrate
  the mechanism; swap in embedding similarity before relying on this in
  production.
- **`extracted_facts` extraction is also heuristic** — the router only
  pulls a candidate fact out of a message if it contains "is/are/was/were/
  has/have." A message like "cats can fly" won't produce a fact; "cats are
  able to fly" will. This is worth knowing if a message you expect to
  become a fact quietly doesn't.
- **Facts are never overwritten in place.** `Fact.update()` bumps the
  version and returns a snapshot of the old one; `SemanticMemory` tracks
  full version history per fact ID.
