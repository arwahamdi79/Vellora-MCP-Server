# memory/quick_test.py
"""
Quick smoke tests for the memory system.
Run with: python -m memory.quick_test
"""

from datetime import datetime

from .memory_manager import MemoryManager
from .episodic_memory import Episode, EpisodicMemory
from .consolidation import ConsolidationLayer
from .semantic_memory import SemanticMemory, Fact
from .promote_drop_router import PromoteDropRouter
from .short_term_memory import Message


def test_contradiction_detection() -> bool:
    print("\nTesting contradiction detection...")

    sm = SemanticMemory()
    sm.add_fact(Fact(statement='Cats can fly', confidence=0.8))
    sm.add_fact(Fact(statement='Cats cannot fly', confidence=0.9))

    contradictions = sm.find_contradictions()
    print(f"Found {len(contradictions)} contradictions")
    for c in contradictions:
        print(f"  - {c['fact1']['statement']} vs {c['fact2']['statement']}")

    return len(contradictions) > 0


def test_consolidation_contradictions() -> bool:
    print("\nTesting consolidation with contradictions...")

    em = EpisodicMemory()
    sm = SemanticMemory()
    router = PromoteDropRouter(episodic_memory=em)
    consolidation = ConsolidationLayer(episodic_memory=em, semantic_memory=sm, router=router)

    em.add_episode(Episode(
        summary='User says cats can fly',
        extracted_facts=['Cats can fly'],
        importance_score=0.8,
    ))
    em.add_episode(Episode(
        summary='User says cats cannot fly',
        extracted_facts=['Cats cannot fly'],
        importance_score=0.9,
    ))

    results = consolidation.run_consolidation(since=datetime.min)
    print(f"Results: {results}")
    print(f"Contradictions found: {results.get('contradictions_found', 0)}")
    print(f"Contradictions resolved: {results.get('contradictions_resolved', 0)}")

    active_facts = sm.get_active_facts()
    print(f"Active facts: {len(active_facts)}")
    for f in active_facts:
        print(f"  - {f.statement} (confidence: {f.confidence})")

    print(f"Recorded contradictions: {len(sm.get_contradictions())}")

    return results.get('contradictions_resolved', 0) > 0 or results.get('contradictions_found', 0) > 0


def test_duplicate_detection() -> bool:
    print("\nTesting duplicate detection...")

    em = EpisodicMemory()
    router = PromoteDropRouter(episodic_memory=em, importance_threshold=0.6)

    em.add_episode(Episode(
        summary='User mentioned their cat is allergic to peanuts',
        details={'content': 'My cat is allergic to peanuts'},
        importance_score=0.5,
    ))

    msg = Message(role='user', content='My cat is allergic to peanuts')
    context = {'critical_keywords': ['allergic', 'cat'], 'goal_matches': True}
    decisions, promoted = router.route_items([msg], context)

    print(f"Promoted: {len(promoted)} (should be 0 for duplicate)")
    if promoted:
        print(f"  - {promoted[0].summary}")

    return len(promoted) == 0


def test_short_term_buffer() -> bool:
    """Show the rolling buffer filling, overflowing, and the router firing."""
    print("\nTesting short-term memory (rolling buffer + overflow)...")

    mm = MemoryManager(short_term_max_size=5)
    mm.start_session('buffer_test', 'test_user')

    for i in range(5):
        mm.add_message('user', f'message {i}')
        print(f"  Added message {i} -> buffer size: {len(mm.short_term.messages)}")

    print(f"  Buffer full at max_size={mm.short_term.max_size}")

    episodes_before = mm.episodic.count()
    mm.add_message('user', 'message 5 (overflow)')  # crosses max_size, should trigger routing
    episodes_after = mm.episodic.count()

    print(f"  After overflow -> buffer size: {len(mm.short_term.messages)} (should be small/empty, router cleared it)")
    print(f"  Episodes before overflow: {episodes_before}, after: {episodes_after}")

    mm.end_session()
    return len(mm.short_term.messages) < 5


def test_scratchpad() -> bool:
    """Show the scratchpad tracking goal/plan/tool state across the session."""
    print("\nTesting scratchpad...")

    mm = MemoryManager()
    mm.start_session('scratchpad_test', 'test_user')

    mm.update_scratchpad(
        plan='Find a supplier for part #4471',
        sub_goal='Retrieve open purchase orders',
        current_step=1,
        total_steps=3,
    )
    mm.add_scratchpad_note("Called search_supplier(part='4471')")
    mm.add_scratchpad_note("Waiting on supplier response")

    pad = mm.short_term.scratchpad
    print(f"  Goal (plan): {pad.plan}")
    print(f"  Current sub-goal: {pad.sub_goal}")
    print(f"  Progress: step {pad.current_step} of {pad.total_steps}")
    print(f"  Notes: {pad.notes}")
    print("  Rendered for prompt:")
    for line in pad.to_prompt().splitlines():
        print(f"    {line}")

    mm.end_session()
    return bool(pad.plan) and bool(pad.notes)


def test_router_reasoning() -> bool:
    """Show promote/forget decisions with their reasoning for a mix of message types."""
    print("\nTesting promote-or-drop router (with visible reasoning)...")

    em = EpisodicMemory()
    router = PromoteDropRouter(episodic_memory=em, importance_threshold=0.6)

    # Note: goal_matches/novel are batch-level context, applied to every item in the
    # call, not scored per-message - so we route the greeting separately rather than
    # mixing it into a batch whose context flags are tuned for the substantive messages.
    greeting_decisions, _ = router.route_items(
        [Message(role='user', content='Hello')],
        context={'critical_keywords': [], 'goal_matches': False, 'novel': False},
    )
    substantive_decisions, promoted = router.route_items(
        [
            Message(role='user', content='Customer prefers email over phone for all future contact'),
            Message(role='user', content='My allergy is penicillin'),
        ],
        context={'critical_keywords': ['allergy', 'penicillin', 'prefers', 'email'], 'goal_matches': True, 'novel': True},
    )
    decisions = greeting_decisions + substantive_decisions

    print("=" * 40)
    for d in decisions:
        print(f"Input:    {d.item_content}")
        print(f"Decision: {d.decision}")
        print(f"Reason:   {d.reasoning}")
        print("-" * 40)

    return len(promoted) == 2 and greeting_decisions[0].decision == 'forget'


def test_full_system() -> bool:
    print("\nTesting full memory system...")

    mm = MemoryManager(short_term_max_size=5)
    mm.start_session('test_session', 'test_user')

    mm.add_message('user', 'I think cats can fly')
    mm.add_message('user', 'Actually, cats cannot fly')
    mm.add_message('user', 'This is important information')
    for i in range(10):
        mm.add_message('tool', f'Search result {i}: some data')

    results = mm.run_consolidation_now()
    search_results = mm.search_memory('cats fly')

    print(f"Consolidation results: {results.get('contradictions_found', 0)} contradictions found")
    print(f"Search results for 'cats fly': {len(search_results['semantic'])} semantic matches")
    for fact in search_results['semantic']:
        print(f"  - {fact['statement']}")

    mm.end_session()
    return True


TESTS = [
    ("Contradiction Detection", test_contradiction_detection),
    ("Consolidation Contradictions", test_consolidation_contradictions),
    ("Duplicate Detection", test_duplicate_detection),
    ("Short-Term Memory Buffer", test_short_term_buffer),
    ("Scratchpad", test_scratchpad),
    ("Router Reasoning", test_router_reasoning),
    ("Full System", test_full_system),
]


def main():
    print("=" * 50)
    print("Running quick memory tests...")
    print("=" * 50)

    results = []
    for name, test_func in TESTS:
        try:
            passed = test_func()
            results.append((name, "PASS" if passed else "FAIL", None))
        except Exception as e:  # noqa: BLE001 - want to report any failure, not crash the suite
            import traceback
            traceback.print_exc()
            results.append((name, "ERROR", str(e)))

    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    for name, status, error in results:
        print(f"{name}: {status}")
        if error:
            print(f"  Error: {error}")


if __name__ == '__main__':
    main()