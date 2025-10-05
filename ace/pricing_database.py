#!/usr/bin/env python3
"""
Pricing Database
SQLite database for storing and querying AI model pricing
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from ace.providers.base_provider import ModelPricing


class PricingDatabase:
    """Database for AI model pricing"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize pricing database.

        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = Path(__file__).parent / "pricing.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Pricing table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pricing (
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_cost_per_1m REAL NOT NULL,
                output_cost_per_1m REAL NOT NULL,
                context_window INTEGER,
                updated_at TIMESTAMP NOT NULL,
                PRIMARY KEY (provider, model)
            )
        """)

        # Pricing update tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pricing_updates (
                provider TEXT PRIMARY KEY,
                last_updated TIMESTAMP NOT NULL,
                next_update TIMESTAMP NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT
            )
        """)

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pricing_provider_model
            ON pricing(provider, model)
        """)

        self.conn.commit()

    def save_pricing(self, provider: str, pricing: Dict[str, ModelPricing]):
        """
        Save pricing data for a provider.

        Args:
            provider: Provider name
            pricing: Dict mapping model name to pricing info
        """
        cursor = self.conn.cursor()

        for model_name, model_pricing in pricing.items():
            cursor.execute("""
                INSERT OR REPLACE INTO pricing
                (provider, model, input_cost_per_1m, output_cost_per_1m,
                 context_window, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                provider,
                model_name,
                model_pricing.input_cost_per_1m,
                model_pricing.output_cost_per_1m,
                model_pricing.context_window,
                model_pricing.updated_at
            ))

        self.conn.commit()

    def get_pricing(self, provider: str, model: str) -> Optional[ModelPricing]:
        """
        Get pricing for a specific model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            ModelPricing or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM pricing
            WHERE provider = ? AND model = ?
        """, (provider, model))

        row = cursor.fetchone()
        if not row:
            return None

        return ModelPricing(
            model=row['model'],
            input_cost_per_1m=row['input_cost_per_1m'],
            output_cost_per_1m=row['output_cost_per_1m'],
            context_window=row['context_window'],
            updated_at=datetime.fromisoformat(row['updated_at'])
        )

    def get_all_pricing(self, provider: Optional[str] = None) -> List[tuple]:
        """
        Get all pricing data.

        Args:
            provider: Optional provider filter

        Returns:
            List of (provider, model, pricing) tuples
        """
        cursor = self.conn.cursor()

        if provider:
            cursor.execute("""
                SELECT * FROM pricing WHERE provider = ?
                ORDER BY provider, model
            """, (provider,))
        else:
            cursor.execute("""
                SELECT * FROM pricing ORDER BY provider, model
            """)

        results = []
        for row in cursor.fetchall():
            pricing = ModelPricing(
                model=row['model'],
                input_cost_per_1m=row['input_cost_per_1m'],
                output_cost_per_1m=row['output_cost_per_1m'],
                context_window=row['context_window'],
                updated_at=datetime.fromisoformat(row['updated_at'])
            )
            results.append((row['provider'], row['model'], pricing))

        return results

    def update_status(
        self,
        provider: str,
        status: str,
        error_message: Optional[str] = None,
        update_interval_days: int = 30
    ):
        """
        Update pricing update status for a provider.

        Args:
            provider: Provider name
            status: Status ('success', 'failed', 'stale')
            error_message: Optional error message if failed
            update_interval_days: Days until next update
        """
        cursor = self.conn.cursor()

        now = datetime.now()
        next_update = now + timedelta(days=update_interval_days)

        cursor.execute("""
            INSERT OR REPLACE INTO pricing_updates
            (provider, last_updated, next_update, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (provider, now, next_update, status, error_message))

        self.conn.commit()

    def get_update_status(self, provider: str) -> Optional[Dict]:
        """
        Get update status for a provider.

        Returns:
            Dict with status info or None
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM pricing_updates WHERE provider = ?
        """, (provider,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'provider': row['provider'],
            'last_updated': datetime.fromisoformat(row['last_updated']),
            'next_update': datetime.fromisoformat(row['next_update']),
            'status': row['status'],
            'error_message': row['error_message']
        }

    def needs_update(self, provider: str) -> bool:
        """
        Check if provider pricing needs update.

        Args:
            provider: Provider name

        Returns:
            True if update needed
        """
        status = self.get_update_status(provider)
        if not status:
            return True  # Never updated

        # Check if past next update time
        return datetime.now() >= status['next_update']

    def get_stale_providers(self) -> List[str]:
        """
        Get list of providers with stale pricing.

        Returns:
            List of provider names
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT provider FROM pricing_updates
            WHERE next_update <= ?
        """, (datetime.now(),))

        return [row['provider'] for row in cursor.fetchall()]

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
