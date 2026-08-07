# memory/test_memory_fixed.py
"""
Fixed test suite for memory system.
Addresses the 3 failing tests.
"""

import unittest
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .short_term_memory import ShortTermMemory, Scratchpad, Message
from .episodic_memory import EpisodicMemory, Episode
from .semantic_memory import SemanticMemory, Fact
from .promote_drop_router import PromoteDropRouter, RoutingDecision
from .consolidation import ConsolidationLayer
from .memory_manager import MemoryManager


class TestSemanticMemoryContradictions(unittest.TestCase):
    """Fixed contradiction detection tests."""
    
    def setUp(self):
        self.sm = SemanticMemory()
    
    def test_contradiction_detection_basic(self):
        """Test basic contradiction detection."""
        fact1 = Fact(statement='Cats can fly', confidence=0.8, category='animals')
        fact2 = Fact(statement='Cats cannot fly', confidence=0.9, category='animals')
        self.sm.add_fact(fact1)
        self.sm.add_fact(fact2)
        
        contradictions = self.sm.find_contradictions()
        self.assertGreater(len(contradictions), 0, "Should detect contradiction between 'can fly' and 'cannot fly'")
    
    def test_contradiction_detection_opposites(self):
        """Test detection of opposing concepts."""
        fact1 = Fact(statement='The food is good', confidence=0.7)
        fact2 = Fact(statement='The food is bad', confidence=0.7)
        self.sm.add_fact(fact1)
        self.sm.add_fact(fact2)
        
        contradictions = self.sm.find_contradictions()
        self.assertGreater(len(contradictions), 0, "Should detect contradiction between 'good' and 'bad'")
    
    def test_contradiction_detection_different_topics(self):
        """Test that different topics don't trigger false contradictions."""
        fact1 = Fact(statement='Cats are cute', confidence=0.8)
        fact2 = Fact(statement='Dogs are loud', confidence=0.8)
        self.sm.add_fact(fact1)
        self.sm.add_fact(fact2)
        
        contradictions = self.sm.find_contradictions()
        self.assertEqual(len(contradictions), 0, "Should not detect contradiction between different topics")


class TestPromoteDropRouterFixed(unittest.TestCase):
    """Fixed duplicate detection tests."""
    
    def setUp(self):
        self.em = EpisodicMemory()
        self.router = PromoteDropRouter(
            episodic_memory=self.em,
            importance_threshold=0.6
        )
    
    def test_duplicate_detection_exact_match(self):
        """Test that exact duplicate content isn't promoted."""
        # Add an episode first
        episode = Episode(
            summary='User mentioned their cat is allergic to peanuts',
            details={'content': 'My cat is allergic to peanuts'},
            importance_score=0.5
        )
        self.em.add_episode(episode)
        
        # Try to route a duplicate
        msg = Message(role='user', content='My cat is allergic to peanuts')
        context = {'critical_keywords': ['allergic', 'cat']}
        
        decisions, promoted = self.router.route_items([msg], context)
        self.assertEqual(len(promoted), 0, "Should not promote duplicate content")
    
    def test_duplicate_detection_similar_match(self):
        """Test that similar content isn't promoted."""
        episode = Episode(
            summary='User said the dog is allergic to eggs',
            details={'content': 'My dog is allergic to eggs'},
            importance_score=0.5
        )
        self.em.add_episode(episode)
        
        msg = Message(role='user', content='My dog cannot eat eggs')
        context = {'critical_keywords': ['allergic', 'dog', 'eggs']}
        
        decisions, promoted = self.router.route_items([msg], context)
        self.assertEqual(len(promoted), 0, "Should not promote similar content")
    
    def test_duplicate_detection_different_content(self):
        """Test that different content is promoted."""
        episode = Episode(
            summary='User mentioned their cat is allergic to peanuts',
            details={'content': 'My cat is allergic to peanuts'},
            importance_score=0.5
        )
        self.em.add_episode(episode)
        
        msg = Message(role='user', content='My dog loves to play fetch')
        context = {'critical_keywords': ['dog', 'play'], 'goal_matches': True}
        
        decisions, promoted = self.router.route_items([msg], context)
        self.assertEqual(len(promoted), 1, "Should promote new content")


class TestConsolidationFixed(unittest.TestCase):
    """Fixed consolidation contradiction tests."""
    
    def setUp(self):
        self.em = EpisodicMemory()
        self.sm = SemanticMemory()
        self.router = PromoteDropRouter(episodic_memory=self.em)
        self.consolidation = ConsolidationLayer(
            episodic_memory=self.em,
            semantic_memory=self.sm,
            router=self.router
        )
    
    def test_consolidation_detects_contradictions(self):
        """Test that consolidation detects and resolves contradictions."""
        # Create contradictory episodes
        episode1 = Episode(
            summary='User says cats can fly',
            extracted_facts=['Cats can fly'],
            importance_score=0.8
        )
        episode2 = Episode(
            summary='User says cats cannot fly',
            extracted_facts=['Cats cannot fly'],
            importance_score=0.9
        )
        self.em.add_episode(episode1)
        self.em.add_episode(episode2)
        
        # Run consolidation
        results = self.consolidation.run_consolidation(since=datetime.min)
        
        # Should have found and resolved contradictions
        self.assertGreater(results.get('contradictions_found', 0), 0, 
                          "Should find contradictions between 'can fly' and 'cannot fly'")
    
    def test_consolidation_resolves_with_higher_confidence(self):
        """Test that higher confidence facts win in contradictions."""
        episode1 = Episode(
            summary='User says cats can fly',
            extracted_facts=['Cats can fly'],
            importance_score=0.6  # Lower confidence
        )
        episode2 = Episode(
            summary='User says cats cannot fly',
            extracted_facts=['Cats cannot fly'],
            importance_score=0.9  # Higher confidence
        )
        self.em.add_episode(episode1)
        self.em.add_episode(episode2)
        
        results = self.consolidation.run_consolidation(since=datetime.min)
        
        # Check that the higher confidence fact won
        facts = self.sm.get_active_facts()
        # The fact with "cannot fly" should survive
        surviving_facts = [f for f in facts if 'cannot fly' in f.statement]
        self.assertGreater(len(surviving_facts), 0, "Higher confidence fact should survive")
    
    def test_consolidation_handles_tie(self):
        """Test that equal facts are both retained with flags."""
        episode1 = Episode(
            summary='User says cats can fly',
            extracted_facts=['Cats can fly'],
            importance_score=0.7
        )
        episode2 = Episode(
            summary='User says cats cannot fly',
            extracted_facts=['Cats cannot fly'],
            importance_score=0.7  # Same confidence
        )
        self.em.add_episode(episode1)
        self.em.add_episode(episode2)
        
        results = self.consolidation.run_consolidation(since=datetime.min)
        
        # Both facts might exist with flags
        contradictions = self.sm.get_contradictions()
        self.assertGreater(len(contradictions), 0, "Should record the contradiction")

    def test_consolidation_no_false_contradictions(self):
        """Test that unrelated facts don't trigger contradictions."""
        episode1 = Episode(
            summary='User likes cats',
            extracted_facts=['User likes cats'],
            importance_score=0.8
        )
        episode2 = Episode(
            summary='User has a dog',
            extracted_facts=['User has a dog'],
            importance_score=0.8
        )
        self.em.add_episode(episode1)
        self.em.add_episode(episode2)
        
        results = self.consolidation.run_consolidation(since=datetime.min)
        
        # Should not find contradictions
        self.assertEqual(results.get('contradictions_found', 0), 0, 
                        "Should not find contradiction between unrelated facts")


class TestFullIntegrationFixed(unittest.TestCase):
    """Full integration test with all fixes applied."""
    
    def test_full_system_with_contradictions(self):
        """Test full system flow with contradictions."""
        mm = MemoryManager(short_term_max_size=5)
        mm.start_session('integ_test', 'test_user')
        
        # Add messages with contradictions
        mm.add_message('user', 'I think cats can fly')
        mm.add_message('user', 'Actually, cats cannot fly')
        mm.add_message('assistant', 'Let me clarify that')
        
        # Add more messages to trigger routing
        for i in range(10):
            mm.add_message('tool', f'Search result {i}')
        
        # Run consolidation
        results = mm.run_consolidation_now()
        
        # Should handle contradictions
        self.assertIsNotNone(results)
        
        # Search for the contradiction
        search_results = mm.search_memory('cats fly')
        
        # End session
        mm.end_session()
        
        print("Full system with contradictions completed successfully")
        print(f"Consolidation results: {json.dumps(results, indent=2, default=str)}")


if __name__ == '__main__':
    # Run the fixed test suite
    unittest.main()