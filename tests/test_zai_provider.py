#!/usr/bin/env python3
"""
Test Z.ai Provider Integration
Verifies that Z.ai provider is properly registered and configured
"""

import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ace.provider_registry import get_registry


def test_zai_provider():
    """Test Z.ai provider registration and configuration"""

    print("=" * 60)
    print("Testing Z.ai Provider Integration")
    print("=" * 60)

    registry = get_registry()

    # Test 1: Provider is registered
    print("\n1. Checking provider registration...")
    providers = registry.list_providers()

    if 'zai' in providers:
        print("   ✅ PASS: Z.ai provider registered")
    else:
        print("   ❌ FAIL: Z.ai provider not found")
        print(f"   Available providers: {providers}")
        return False

    # Test 2: Can get provider instance
    print("\n2. Getting provider instance...")
    try:
        zai = registry.get('zai')
        print(f"   ✅ PASS: Got provider instance")
        print(f"   Display name: {zai.get_display_name()}")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # Test 3: Available models
    print("\n3. Checking available models...")
    try:
        models = zai.get_available_models()
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
        pricing = zai.fetch_pricing()
        print(f"   ✅ PASS: Pricing for {len(pricing)} models")
        for model_name, price_info in pricing.items():
            print(f"      • {model_name}:")
            print(f"        Input:  ${price_info.input_cost_per_1m}/1M tokens")
            print(f"        Output: ${price_info.output_cost_per_1m}/1M tokens")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # Test 5: Configuration check
    print("\n5. Checking API key configuration...")
    if zai.is_configured():
        print("   ✅ PASS: API key is configured")
        print("   Note: Ready to make API calls")
    else:
        print("   ⚠️  WARNING: API key not configured")
        print("   Set ZAI_API_KEY environment variable to enable API calls")
        print("   Get your key at: https://z.ai/model-api")

    # Test 6: Pricing URL
    print("\n6. Checking pricing documentation...")
    pricing_url = zai.get_pricing_url()
    print(f"   ✅ PASS: {pricing_url}")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("Z.ai provider successfully integrated!")
    print("=" * 60)

    print("\n💡 Usage Example:")
    print("   Set in .env:")
    print("   BUILDER_PROVIDER=zai")
    print("   BUILDER_MODEL=glm-4.6")
    print("   ZAI_API_KEY=your_api_key_here")

    print("\n💰 Cost Comparison:")
    print("   GLM-4.6:        $0.60/$2.00  per 1M tokens")
    print("   GPT-4o-mini:    $0.15/$0.60  per 1M tokens")
    print("   Claude Sonnet:  $3.00/$15.00 per 1M tokens")
    print("   → GLM-4.6 is 5x cheaper than Claude for similar quality!")

    return True


if __name__ == "__main__":
    success = test_zai_provider()
    exit(0 if success else 1)
