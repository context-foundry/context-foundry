#!/usr/bin/env python3
"""
Pricing Fetcher
Fetches pricing data from provider websites and stores in database
"""

import os
from typing import Dict, Optional
from datetime import datetime
from ace.pricing_database import PricingDatabase
from ace.provider_registry import get_registry


class PricingFetcher:
    """Fetches and updates pricing data from all providers"""

    def __init__(self, db: Optional[PricingDatabase] = None):
        """
        Initialize pricing fetcher.

        Args:
            db: PricingDatabase instance (creates new if None)
        """
        self.db = db or PricingDatabase()
        self.registry = get_registry()

    def fetch_all(self, force: bool = False) -> Dict[str, Dict]:
        """
        Fetch pricing from all providers.

        Args:
            force: Force update even if not stale

        Returns:
            Dict mapping provider name to fetch result
        """
        results = {}

        for provider_name in self.registry.list_providers():
            # Check if update needed
            if not force and not self.db.needs_update(provider_name):
                results[provider_name] = {
                    'status': 'skipped',
                    'message': 'Pricing is up to date'
                }
                continue

            # Fetch pricing
            result = self.fetch_provider(provider_name)
            results[provider_name] = result

        return results

    def fetch_provider(self, provider_name: str) -> Dict:
        """
        Fetch pricing for a single provider.

        Args:
            provider_name: Provider name

        Returns:
            Dict with fetch result
        """
        try:
            provider = self.registry.get(provider_name)

            print(f"Fetching pricing for {provider_name}...")

            # Fetch pricing from provider
            pricing = provider.fetch_pricing()

            # Save to database
            self.db.save_pricing(provider_name, pricing)

            # Update status
            self.db.update_status(
                provider_name,
                status='success',
                update_interval_days=int(os.getenv('PRICING_UPDATE_DAYS', '30'))
            )

            return {
                'status': 'success',
                'models_updated': len(pricing),
                'updated_at': datetime.now()
            }

        except Exception as e:
            # Log error
            self.db.update_status(
                provider_name,
                status='failed',
                error_message=str(e)
            )

            return {
                'status': 'failed',
                'error': str(e)
            }

    def auto_update(self) -> Optional[Dict[str, Dict]]:
        """
        Auto-update stale pricing if enabled.

        Returns:
            Update results if auto-update enabled, None otherwise
        """
        # Check if auto-update is enabled
        if not os.getenv('PRICING_AUTO_UPDATE', 'true').lower() in ('true', '1', 'yes'):
            return None

        # Get stale providers
        stale = self.db.get_stale_providers()

        if not stale:
            return None

        print(f"Auto-updating pricing for {len(stale)} providers...")

        # Fetch only stale providers
        results = {}
        for provider_name in stale:
            if provider_name in self.registry.list_providers():
                results[provider_name] = self.fetch_provider(provider_name)

        return results

    def get_pricing_status(self) -> Dict[str, Dict]:
        """
        Get pricing status for all providers.

        Returns:
            Dict mapping provider to status info
        """
        status = {}

        for provider_name in self.registry.list_providers():
            provider_status = self.db.get_update_status(provider_name)

            if provider_status:
                status[provider_name] = {
                    'last_updated': provider_status['last_updated'],
                    'next_update': provider_status['next_update'],
                    'status': provider_status['status'],
                    'needs_update': self.db.needs_update(provider_name)
                }
            else:
                status[provider_name] = {
                    'status': 'never_updated',
                    'needs_update': True
                }

        return status
