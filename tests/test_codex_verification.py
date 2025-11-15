"""
Test suite to verify Codex database integrity and pattern existence.

This test suite addresses auditor findings about Codex database verification.
It confirms that patterns exported to JSON actually exist in the database.
"""

import sqlite3
from pathlib import Path


def get_codex_db_path():
    """Get path to Codex database."""
    return Path.home() / ".context-foundry" / "codex.db"


def test_codex_database_exists():
    """Verify Codex database file exists."""
    db_path = get_codex_db_path()
    assert db_path.exists(), f"Codex database not found at {db_path}"


def test_codex_has_entries():
    """Verify Codex database has entries."""
    db_path = get_codex_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM knowledge_entries")
    count = cursor.fetchone()[0]

    conn.close()

    assert count > 0, "Codex database has no entries"
    print(f"✅ Codex database has {count} entries")


def test_santa_dashboard_patterns_exist():
    """
    Verify that patterns mentioned in Santa Dashboard BUILD_POSTMORTEM
    actually exist in the Codex database.

    This addresses the auditor's finding:
    'Codex lessons cited are only visible in JSON, not demonstrably in Codex'
    """
    db_path = get_codex_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Patterns mentioned in BUILD_POSTMORTEM.md
    expected_patterns = [
        "iss-cf-daemon-incorrectly-marks-321",
        "pat-claude-code-subprocess-delegat-159",
        "pat-websocket-broadcasting-for-rea-280",
    ]

    missing_patterns = []
    for pattern_id in expected_patterns:
        cursor.execute(
            "SELECT id, title FROM knowledge_entries WHERE id = ?", (pattern_id,)
        )
        result = cursor.fetchone()

        if result:
            print(f"✅ Found: {result[0]} - {result[1]}")
        else:
            missing_patterns.append(pattern_id)
            print(f"❌ Missing: {pattern_id}")

    conn.close()

    assert len(missing_patterns) == 0, f"Missing patterns in Codex: {missing_patterns}"


def test_codex_pattern_counts():
    """Verify Codex has expected number of issues and patterns."""
    db_path = get_codex_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT type, COUNT(*) FROM knowledge_entries GROUP BY type")
    counts = dict(cursor.fetchall())

    conn.close()

    # We should have issues and patterns
    assert "issue" in counts, "No issues found in Codex"
    assert "pattern" in counts, "No patterns found in Codex"

    print(f"✅ Codex contains {counts.get('issue', 0)} issues")
    print(f"✅ Codex contains {counts.get('pattern', 0)} patterns")

    # Based on current state
    assert counts.get("issue", 0) >= 30, "Expected at least 30 issues"
    assert counts.get("pattern", 0) >= 10, "Expected at least 10 patterns"


def test_daemon_issue_exists():
    """Verify the critical daemon bug from Santa Dashboard is documented."""
    db_path = get_codex_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, description, severity
        FROM knowledge_entries
        WHERE id LIKE '%daemon%' AND id LIKE '%marks%'
        """
    )
    results = cursor.fetchall()

    conn.close()

    assert len(results) > 0, "Daemon status bug not found in Codex"

    for row in results:
        print(f"✅ Found daemon issue: {row[0]}")
        print(f"   Title: {row[1]}")
        print(f"   Severity: {row[3]}")


if __name__ == "__main__":
    print("=" * 60)
    print("Codex Database Verification Tests")
    print("=" * 60)
    print()

    tests = [
        test_codex_database_exists,
        test_codex_has_entries,
        test_santa_dashboard_patterns_exist,
        test_codex_pattern_counts,
        test_daemon_issue_exists,
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\nRunning: {test.__name__}")
        print("-" * 60)
        try:
            test()
            print(f"✅ PASSED: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {test.__name__}")
            print(f"   {type(e).__name__}: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
