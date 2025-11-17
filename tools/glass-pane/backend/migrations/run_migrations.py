#!/usr/bin/env python3
"""
Migration runner for Glass Pane database.

Automatically applies pending SQL migrations from the migrations/ directory
and tracks which migrations have been applied.

Usage:
    python3 migrations/run_migrations.py                    # Run all pending migrations
    python3 migrations/run_migrations.py --list             # List migration status
    python3 migrations/run_migrations.py --force <name>     # Force re-run a migration
"""

import sqlite3
import sys
from pathlib import Path
import argparse


def get_db_path():
    """Get the database path from config."""
    # Import config to respect environment variables
    import sys
    from pathlib import Path

    # Add backend directory to path to import config
    backend_dir = Path(__file__).parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from config import settings

    return settings.expanded_db_path


def ensure_migrations_table(conn: sqlite3.Connection):
    """Create schema_migrations table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filename TEXT NOT NULL
        )
    """)
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection) -> set:
    """Get set of already-applied migration versions."""
    cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cursor.fetchall()}


def get_available_migrations(migrations_dir: Path) -> list:
    """
    Get list of available migration files.

    Returns list of tuples: (version, filename, filepath)
    Migration files should be named like: 001_add_chat_tables.sql
    """
    migrations = []

    for sql_file in sorted(migrations_dir.glob("*.sql")):
        # Extract version from filename (e.g., "001" from "001_add_chat_tables.sql")
        version = sql_file.stem.split("_")[0]

        migrations.append((version, sql_file.name, sql_file))

    return sorted(migrations, key=lambda x: x[0])


def apply_migration(
    conn: sqlite3.Connection, version: str, filename: str, filepath: Path
):
    """Apply a single migration file."""
    print(f"Applying migration {version}: {filename}...")

    try:
        # Read migration file
        with open(filepath, "r") as f:
            sql = f.read()

        # Execute migration
        conn.executescript(sql)

        # Record migration
        conn.execute(
            "INSERT INTO schema_migrations (version, filename) VALUES (?, ?)",
            (version, filename),
        )
        conn.commit()

        print(f"  ✓ Successfully applied {filename}")
        return True

    except Exception as e:
        print(f"  ✗ Failed to apply {filename}: {e}")
        conn.rollback()
        return False


def list_migrations(conn: sqlite3.Connection, migrations_dir: Path):
    """List all migrations and their status."""
    applied = get_applied_migrations(conn)
    available = get_available_migrations(migrations_dir)

    print("\nMigration Status:")
    print("-" * 80)
    print(f"{'Version':<10} {'Status':<15} {'Filename':<50}")
    print("-" * 80)

    for version, filename, _ in available:
        status = "✓ Applied" if version in applied else "○ Pending"
        print(f"{version:<10} {status:<15} {filename:<50}")

    print("-" * 80)
    print(
        f"\nTotal: {len(available)} migrations ({len(applied)} applied, {len(available) - len(applied)} pending)"
    )


def run_migrations(force_version: str = None):
    """Run all pending migrations or force re-run a specific migration."""
    # Get paths
    migrations_dir = Path(__file__).parent
    db_path = get_db_path()

    print(f"Database: {db_path}")
    print(f"Migrations directory: {migrations_dir}\n")

    # Connect to database
    conn = sqlite3.connect(db_path)

    try:
        # Ensure migrations table exists
        ensure_migrations_table(conn)

        # Get migration status
        applied = get_applied_migrations(conn)
        available = get_available_migrations(migrations_dir)

        if not available:
            print("No migration files found in migrations/ directory")
            return

        # Force re-run specific migration
        if force_version:
            migration = next((m for m in available if m[0] == force_version), None)
            if not migration:
                print(f"Error: Migration version '{force_version}' not found")
                return

            version, filename, filepath = migration
            print(f"Force re-running migration {version}...")

            # Delete from schema_migrations if it exists
            conn.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))
            conn.commit()

            # Apply migration
            apply_migration(conn, version, filename, filepath)
            return

        # Apply pending migrations
        pending = [(v, f, p) for v, f, p in available if v not in applied]

        if not pending:
            print("✓ All migrations are up to date!")
            return

        print(f"Found {len(pending)} pending migration(s):\n")

        for version, filename, filepath in pending:
            success = apply_migration(conn, version, filename, filepath)
            if not success:
                print("\n✗ Migration failed. Stopping.")
                sys.exit(1)

        print(f"\n✓ Successfully applied {len(pending)} migration(s)!")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Run Glass Pane database migrations")
    parser.add_argument(
        "--list", action="store_true", help="List all migrations and their status"
    )
    parser.add_argument(
        "--force",
        metavar="VERSION",
        help="Force re-run a specific migration version (e.g., '001')",
    )

    args = parser.parse_args()

    # Get paths
    migrations_dir = Path(__file__).parent
    db_path = get_db_path()

    # Connect to database
    conn = sqlite3.connect(db_path)

    try:
        ensure_migrations_table(conn)

        if args.list:
            list_migrations(conn, migrations_dir)
        elif args.force:
            conn.close()
            run_migrations(force_version=args.force)
        else:
            conn.close()
            run_migrations()
    finally:
        # Close connection if it wasn't already closed
        if conn:
            try:
                conn.close()
            except Exception:
                pass  # Connection already closed


if __name__ == "__main__":
    main()
