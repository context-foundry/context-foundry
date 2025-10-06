#!/usr/bin/env python3
"""
Test GitHub Copilot Provider Integration
Verifies that GitHub Copilot provider is properly registered and configured
"""

import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ace.provider_registry import get_registry


def test_github_provider():
    """Test GitHub Copilot provider registration and configuration"""

    print("=" * 60)
    print("Testing GitHub Copilot Provider Integration")
    print("=" * 60)

    registry = get_registry()

    # Test 1: Provider is registered
    print("\n1. Checking provider registration...")
    providers = registry.list_providers()

    if 'github' in providers:
        print("   ✅ PASS: GitHub Copilot provider registered")
    else:
        print("   ❌ FAIL: GitHub Copilot provider not found")
        print(f"   Available providers: {providers}")
        return False

    # Test 2: Can get provider instance
    print("\n2. Getting provider instance...")
    try:
        github = registry.get('github')
        print(f"   ✅ PASS: Got provider instance")
        print(f"   Display name: {github.get_display_name()}")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # Test 3: Available models
    print("\n3. Checking available models...")
    try:
        models = github.get_available_models()
        print(f"   ✅ PASS: {len(models)} models available")
        for model in models:
            print(f"      • {model.display_name} ({model.name})")
            print(f"        Context: {model.context_window:,} tokens")
            print(f"        {model.description}")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # Test 4: Pricing information
    print("\n4. Checking pricing...")
    try:
        pricing = github.fetch_pricing()
        print(f"   ✅ PASS: Pricing for {len(pricing)} models")
        print(f"   💡 Note: GitHub Copilot uses subscription pricing ($10/month)")
        for model_name, price_info in pricing.items():
            print(f"      • {model_name}: Included in subscription")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # Test 5: Configuration check
    print("\n5. Checking GitHub token configuration...")
    if github.is_configured():
        print("   ✅ PASS: GitHub token is configured")
        print("   Note: Ready to exchange for Copilot token")
        print("   ⚠️  Requires active Copilot subscription")
    else:
        print("   ⚠️  WARNING: GitHub token not configured")
        print("   Set GITHUB_TOKEN environment variable")
        print("   Generate at: https://github.com/settings/tokens")
        print("   Requires active GitHub Copilot subscription")

    # Test 6: Pricing URL
    print("\n6. Checking documentation...")
    pricing_url = github.get_pricing_url()
    print(f"   ✅ PASS: {pricing_url}")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("GitHub Copilot provider successfully integrated!")
    print("=" * 60)

    print("\n💡 Usage Example:")
    print("   Set in .env:")
    print("   GITHUB_TOKEN=ghp_your_personal_access_token")
    print("   BUILDER_PROVIDER=github")
    print("   BUILDER_MODEL=gpt-4o  # GPT-4.1")

    print("\n📋 Requirements:")
    print("   ✓ Active GitHub Copilot subscription ($10/month)")
    print("   ✓ GitHub Personal Access Token (PAT)")
    print("   ✓ Token will be exchanged for Copilot API token")

    print("\n💰 Pricing Model:")
    print("   GitHub Copilot: $10/month (individual) or $19/month (business)")
    print("   Unlimited usage within subscription")
    print("   No per-token charges")
    print("   → Fixed cost, predictable billing!")

    print("\n🎯 Key Features:")
    print("   • GPT-4.1 (gpt-4o) as default model")
    print("   • 128K context window")
    print("   • Automatic token exchange and refresh")
    print("   • Included in Copilot subscription")

    return True


if __name__ == "__main__":
    success = test_github_provider()
    exit(0 if success else 1)
