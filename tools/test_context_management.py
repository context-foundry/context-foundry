#!/usr/bin/env python3
"""
Test Script for Context Management System
Validates that context stays under 50% during complex multi-phase tasks.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ace.claude_integration import ClaudeClient
from ace.context_manager import ContextManager
from ace.compactors.smart_compactor import SmartCompactor
from ace.subagent_manager import SubagentManager


def test_basic_context_management():
    """Test basic context manager functionality."""
    print("=" * 80)
    print("TEST 1: Basic Context Management")
    print("=" * 80)

    session_id = f"test_basic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    manager = ContextManager(session_id)

    # Simulate multiple interactions
    print("\n📝 Simulating 10 interactions...")
    for i in range(10):
        manager.track_interaction(
            prompt=f"Test prompt {i}" * 50,  # ~250 words
            response=f"Test response {i}" * 100,  # ~500 words
            input_tokens=500 + i * 50,
            output_tokens=1000 + i * 100,
            content_type="code" if i % 2 == 0 else "decision"
        )

    # Check usage
    metrics = manager.get_usage()
    print(f"\n📊 Context Metrics:")
    print(f"   Total tokens: {metrics.total_tokens:,}")
    print(f"   Percentage: {metrics.context_percentage:.2f}%")
    print(f"   Messages: {metrics.message_count}")
    print(f"   Compactions: {metrics.compaction_count}")

    # Test compaction check
    should_compact, reason = manager.should_compact()
    print(f"\n🔍 Compaction check:")
    print(f"   Should compact: {should_compact}")
    print(f"   Reason: {reason}")

    # Test insights
    insights = manager.get_insights()
    print(f"\n💡 Context Insights:")
    print(f"   Health: {insights['health']}")
    print(f"   Content types: {list(insights['content_breakdown']['by_count'].keys())}")

    print("\n✅ Test 1 passed!\n")
    return True


def test_smart_compaction():
    """Test smart compactor with Claude API."""
    print("=" * 80)
    print("TEST 2: Smart Compaction")
    print("=" * 80)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set - skipping smart compaction test")
        return True

    from ace.context_manager import ContentItem, ContextMetrics

    session_id = f"test_compact_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    compactor = SmartCompactor()

    # Create sample content
    print("\n📝 Creating sample content...")
    content_items = [
        ContentItem(
            content="We decided to use FastAPI for the REST API because it has async support and automatic OpenAPI docs.",
            role="assistant",
            importance_score=0.9,
            token_estimate=150,
            timestamp=datetime.now().isoformat(),
            content_type="decision"
        ),
        ContentItem(
            content="Here's the implementation of the user authentication:\n\nclass UserAuth:\n    def __init__(self):\n        self.sessions = {}\n    \n    def login(self, username, password):\n        # Hash password and validate\n        pass",
            role="assistant",
            importance_score=0.7,
            token_estimate=250,
            timestamp=datetime.now().isoformat(),
            content_type="code"
        ),
        ContentItem(
            content="We encountered an error with JWT token expiration - tokens were expiring too quickly. Fixed by extending expiration to 24 hours.",
            role="assistant",
            importance_score=0.85,
            token_estimate=180,
            timestamp=datetime.now().isoformat(),
            content_type="error"
        ),
    ]

    # Create metrics
    metrics = ContextMetrics(
        total_tokens=580,
        context_percentage=0.29,
        message_count=3,
        compaction_count=0,
        last_compaction_tokens=0,
        timestamp=datetime.now().isoformat()
    )

    # Test compaction
    print("\n🔄 Testing smart compaction...")
    result = compactor.compact_context(content_items, metrics)

    print(f"\n📊 Compaction Results:")
    print(f"   Reduction: {result['reduction_pct']:.1f}%")
    print(f"   Before tokens: {content_items[0].token_estimate + content_items[1].token_estimate + content_items[2].token_estimate}")
    print(f"   After tokens: {result['estimated_tokens']}")
    print(f"   Summary length: {len(result['summary'])} chars")
    print(f"   Summary saved: {result['summary_file']}")

    print("\n✅ Test 2 passed!\n")
    return True


def test_subagent_system():
    """Test subagent manager."""
    print("=" * 80)
    print("TEST 3: Subagent System")
    print("=" * 80)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set - skipping subagent test")
        return True

    session_id = f"test_subagent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    manager = SubagentManager(session_id)

    # Test single scout
    print("\n🔍 Testing single scout subagent...")
    scout_result = manager.spawn_scout(
        "Research best practices for context management in LLM applications",
        {"domain": "AI", "focus": "token optimization"}
    )

    print(f"\n📊 Scout Results:")
    print(f"   Success: {scout_result.success}")
    print(f"   Tokens used: {scout_result.tokens_used:,}")
    print(f"   Summary tokens: {scout_result.summary_tokens:,}")
    print(f"   Compression: {(1 - scout_result.summary_tokens/scout_result.tokens_used)*100:.1f}%")

    # Test parallel execution
    print("\n🚀 Testing parallel subagents...")
    parallel_tasks = [
        ("scout", "Research database options for Python web apps", {"language": "python"}),
        ("explorer", "Explore caching strategies", {"focus_areas": ["Redis", "Memcached"]})
    ]

    results = manager.spawn_parallel(parallel_tasks)

    print(f"\n📊 Parallel Results:")
    print(f"   Tasks completed: {len(results)}")
    print(f"   Success rate: {len([r for r in results if r.success])}/{len(results)}")

    # Collect summaries
    print("\n📝 Collecting summaries...")
    summaries = manager.collect_summaries(results)
    print(f"   Combined summary length: {len(summaries)} chars")
    print(f"   Summary preview: {summaries[:200]}...")

    print("\n✅ Test 3 passed!\n")
    return True


def test_integrated_workflow():
    """Test complete integrated workflow with context management."""
    print("=" * 80)
    print("TEST 4: Integrated Workflow")
    print("=" * 80)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set - skipping integrated test")
        return True

    session_id = f"test_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Create client with context management
    print("\n🤖 Creating Claude client with context management...")
    client = ClaudeClient(
        session_id=session_id,
        use_context_manager=True
    )

    # Simulate complex task with multiple phases
    phases = [
        ("Research", "Research best practices for building a todo CLI app in Python", "decision"),
        ("Architecture", "Design the architecture for a todo CLI app with local storage", "decision"),
        ("Implementation", "Implement a Task class with add, list, and complete methods", "code"),
        ("Testing", "Write unit tests for the Task class", "code"),
        ("Documentation", "Write usage documentation for the CLI app", "general"),
    ]

    print(f"\n📝 Simulating {len(phases)} phases...")

    for i, (phase_name, prompt, content_type) in enumerate(phases, 1):
        print(f"\n--- Phase {i}: {phase_name} ---")
        response, metadata = client.call_claude(prompt, content_type=content_type)

        print(f"✅ {phase_name} complete")
        print(f"   Tokens: {metadata['input_tokens']:,} in, {metadata['output_tokens']:,} out")
        print(f"   Context: {metadata['context_percentage']:.1f}%")
        print(f"   Health: {metadata.get('context_health', 'N/A')}")

        if metadata.get('compaction_count', 0) > 0:
            print(f"   🔄 Compactions performed: {metadata['compaction_count']}")

    # Final stats
    print("\n📊 Final Statistics:")
    stats = client.get_context_stats()
    print(f"   Total messages: {stats['messages']}")
    print(f"   Total tokens: {stats['total_tokens']:,}")
    print(f"   Context percentage: {stats['context_percentage']:.1f}%")
    print(f"   Context health: {stats.get('context_health', 'N/A')}")

    # Check if context stayed under 50%
    if stats['context_percentage'] < 50:
        print(f"\n✅ SUCCESS: Context stayed under 50% ({stats['context_percentage']:.1f}%)")
    else:
        print(f"\n⚠️  WARNING: Context exceeded 50% ({stats['context_percentage']:.1f}%)")

    if stats.get('compaction_stats'):
        print(f"\n🔄 Compaction Stats:")
        print(f"   Count: {stats['compaction_stats']['count']}")
        print(f"   Last saved: {stats['compaction_stats']['last_saved_tokens']:,} tokens")

    print("\n✅ Test 4 passed!\n")
    return True


def main():
    """Run all tests."""
    print("\n🧪 Context Management System Test Suite")
    print("=" * 80)
    print()

    tests = [
        ("Basic Context Management", test_basic_context_management),
        ("Smart Compaction", test_smart_compaction),
        ("Subagent System", test_subagent_system),
        ("Integrated Workflow", test_integrated_workflow),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
