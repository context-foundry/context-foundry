"""
Test suite to verify Codex database integrity and pattern existence.

This test suite addresses auditor findings about Codex database verification.
It confirms that patterns exported to JSON actually exist in the database.

NOTE: These are integration tests that require the actual Codex database.
To run in pytest, set REAL_HOME environment variable:
    REAL_HOME=$HOME pytest tests/test_codex_verification.py -v
"""

import os
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def codex_db_path():
    """Get path to Codex database, handling pytest home isolation.

    Returns the path to the real user's codex.db, not pytest's isolated temp home.
    """
    # Check if we're in pytest's isolated environment
    current_home = Path.home()
    if "pytest" in str(current_home) or "tmp" in str(current_home):
        # Use REAL_HOME env var if set (for CI/testing)
        real_home = os.environ.get("REAL_HOME")
        if real_home:
            return Path(real_home) / ".context-foundry" / "codex.db"

        # Skip tests if database doesn't exist
        pytest.skip("Codex database not found - set REAL_HOME to run integration tests")

    return current_home / ".context-foundry" / "codex.db"


@pytest.fixture(scope="module")
def db_connection(codex_db_path):
    """Create database connection fixture."""
    if not codex_db_path.exists():
        pytest.skip(f"Codex database not found at {codex_db_path}")

    conn = sqlite3.connect(str(codex_db_path))
    yield conn
    conn.close()


def test_codex_database_exists(codex_db_path):
    """Verify Codex database file exists."""
    assert codex_db_path.exists(), f"Codex database not found at {codex_db_path}"


def test_codex_has_entries(db_connection):
    """Verify Codex database has entries."""
    cursor = db_connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM knowledge_entries")
    count = cursor.fetchone()[0]

    assert count > 0, "Codex database has no entries"
    print(f"✅ Codex database has {count} entries")


def test_santa_dashboard_patterns_exist(db_connection):
    """
    Verify that patterns mentioned in Santa Dashboard BUILD_POSTMORTEM
    actually exist in the Codex database.

    This addresses the auditor's finding:
    'Codex lessons cited are only visible in JSON, not demonstrably in Codex'
    """
    cursor = db_connection.cursor()

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

    assert len(missing_patterns) == 0, f"Missing patterns in Codex: {missing_patterns}"


def test_codex_pattern_counts(db_connection):
    """Verify Codex has expected number of issues and patterns."""
    cursor = db_connection.cursor()
    cursor.execute("SELECT type, COUNT(*) FROM knowledge_entries GROUP BY type")
    counts = dict(cursor.fetchall())

    # We should have issues and patterns
    assert "issue" in counts, "No issues found in Codex"
    assert "pattern" in counts, "No patterns found in Codex"

    print(f"✅ Codex contains {counts.get('issue', 0)} issues")
    print(f"✅ Codex contains {counts.get('pattern', 0)} patterns")

    # Based on current state
    assert counts.get("issue", 0) >= 30, "Expected at least 30 issues"
    assert counts.get("pattern", 0) >= 10, "Expected at least 10 patterns"


def test_daemon_issue_exists(db_connection):
    """Verify the critical daemon bug from Santa Dashboard is documented."""
    cursor = db_connection.cursor()
    cursor.execute(
        """
        SELECT id, title, description, severity
        FROM knowledge_entries
        WHERE id LIKE '%daemon%' AND id LIKE '%marks%'
        """
    )
    results = cursor.fetchall()

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

    # Get real codex path (no pytest isolation when run directly)
    codex_path = Path.home() / ".context-foundry" / "codex.db"

    if not codex_path.exists():
        print(f"❌ Codex database not found at {codex_path}")
        print("Cannot run tests without database.")
        exit(1)

    # Create connection
    conn = sqlite3.connect(str(codex_path))

    tests = [
        ("Database exists", lambda: test_codex_database_exists(codex_path)),
        ("Has entries", lambda: test_codex_has_entries(conn)),
        ("Santa patterns exist", lambda: test_santa_dashboard_patterns_exist(conn)),
        ("Pattern counts", lambda: test_codex_pattern_counts(conn)),
        ("Daemon issue exists", lambda: test_daemon_issue_exists(conn)),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\nRunning: {name}")
        print("-" * 60)
        try:
            test_func()
            print(f"✅ PASSED: {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {name}")
            print(f"   {type(e).__name__}: {e}")
            failed += 1

    conn.close()

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
