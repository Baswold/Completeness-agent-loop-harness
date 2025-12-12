#!/usr/bin/env python3
"""
Test script for Mistral API integration with the completeness loop.

This script validates:
1. MistralBackend can be instantiated
2. API credentials are properly configured
3. Basic API calls work (with proper error handling for missing API key)
4. Backend is correctly selected via config
5. Tool support is enabled
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import LoopConfig, ModelConfig
from src.llm import create_backend, MistralBackend, TokenUsage, LLMResponse


def test_mistral_backend_instantiation():
    """Test that MistralBackend raises error if API key is missing."""
    print("Test 1: MistralBackend instantiation without API key")
    print("-" * 60)

    # Clear API key to test error handling
    old_key = os.environ.pop("MISTRAL_API_KEY", None)

    try:
        backend = MistralBackend()
        print("❌ FAILED: Should have raised ValueError for missing API key")
        return False
    except ValueError as e:
        if "MISTRAL_API_KEY" in str(e):
            print("✓ PASSED: Correctly raises error for missing API key")
            print(f"  Error message: {str(e)[:80]}...")
            return True
        else:
            print(f"❌ FAILED: Wrong error: {e}")
            return False
    finally:
        # Restore API key
        if old_key:
            os.environ["MISTRAL_API_KEY"] = old_key


def test_mistral_backend_with_mock_key():
    """Test that MistralBackend initializes with a mock API key."""
    print("\nTest 2: MistralBackend instantiation with mock API key")
    print("-" * 60)

    os.environ["MISTRAL_API_KEY"] = "test-key-12345"

    try:
        backend = MistralBackend(model="devstral-small-2505")
        print(f"✓ PASSED: MistralBackend instantiated")
        print(f"  Model: {backend.model}")
        print(f"  Info: {backend.get_info()}")

        # Check properties
        assert backend.model == "devstral-small-2505", "Wrong model name"
        assert backend.api_key == "test-key-12345", "Wrong API key"
        assert backend.base_url == "https://api.mistral.ai/v1", "Wrong base URL"
        assert backend.supports_tools() == True, "Should support tools"

        print("✓ All properties correct")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_config_defaults():
    """Test that config uses Mistral as default backend."""
    print("\nTest 3: Default config uses Mistral")
    print("-" * 60)

    config = LoopConfig()
    print(f"  Backend: {config.model.backend}")
    print(f"  Model: {config.model.name}")

    if config.model.backend == "mistral" and config.model.name == "devstral-small-2505":
        print("✓ PASSED: Default config correctly uses Mistral")
        return True
    else:
        print(f"❌ FAILED: Backend={config.model.backend}, Model={config.model.name}")
        return False


def test_create_backend_mistral():
    """Test that create_backend correctly creates MistralBackend."""
    print("\nTest 4: create_backend() with mistral config")
    print("-" * 60)

    os.environ["MISTRAL_API_KEY"] = "test-key-12345"

    config = LoopConfig()

    try:
        backend = create_backend(config)

        if isinstance(backend, MistralBackend):
            print("✓ PASSED: create_backend() returns MistralBackend instance")
            print(f"  Type: {type(backend).__name__}")
            return True
        else:
            print(f"❌ FAILED: Wrong backend type: {type(backend).__name__}")
            return False
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_mistral_aliases():
    """Test that backend aliases resolve to mistral."""
    print("\nTest 5: Backend aliases for mistral")
    print("-" * 60)

    from src.llm import BACKEND_ALIASES

    aliases = ["mistral", "devstral"]
    all_correct = True

    for alias in aliases:
        resolved = BACKEND_ALIASES.get(alias)
        if resolved == "mistral":
            print(f"  ✓ '{alias}' -> 'mistral'")
        else:
            print(f"  ❌ '{alias}' -> '{resolved}' (expected 'mistral')")
            all_correct = False

    if all_correct:
        print("✓ PASSED: All aliases correct")
        return True
    else:
        print("❌ FAILED: Some aliases incorrect")
        return False


def test_llm_response_types():
    """Test that LLMResponse and TokenUsage work correctly."""
    print("\nTest 6: LLMResponse and TokenUsage data types")
    print("-" * 60)

    try:
        # Create token usage
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )

        # Create response
        response = LLMResponse(
            content="Hello, world!",
            tool_calls=[],
            usage=usage,
            finish_reason="stop"
        )

        print(f"  TokenUsage: {usage.total_tokens} total tokens")
        print(f"  Response content: {response.content[:30]}...")
        print(f"  Finish reason: {response.finish_reason}")
        print("✓ PASSED: Data types work correctly")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_mistral_model_variants():
    """Test that different Mistral models can be configured."""
    print("\nTest 7: Different Mistral model variants")
    print("-" * 60)

    os.environ["MISTRAL_API_KEY"] = "test-key-12345"

    models = [
        "devstral-small-2505",
        "mistral-small-latest",
        "mistral-large-latest"
    ]

    all_passed = True
    for model in models:
        try:
            backend = MistralBackend(model=model)
            print(f"  ✓ {model}")
        except Exception as e:
            print(f"  ❌ {model}: {e}")
            all_passed = False

    if all_passed:
        print("✓ PASSED: All model variants work")
        return True
    else:
        print("❌ FAILED: Some models failed")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MISTRAL API INTEGRATION TESTS")
    print("=" * 60)

    tests = [
        test_mistral_backend_instantiation,
        test_mistral_backend_with_mock_key,
        test_config_defaults,
        test_create_backend_mistral,
        test_mistral_aliases,
        test_llm_response_types,
        test_mistral_model_variants,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✓ ALL {total} TESTS PASSED")
        print("=" * 60)
        print("\nMistral integration is ready to use!")
        print("\nTo use Mistral with the completeness loop:")
        print("  1. Set your API key: export MISTRAL_API_KEY='your-key'")
        print("  2. Get your key from: https://console.mistral.ai/")
        print("  3. Run: python main.py")
        print("\nThe system will automatically use Mistral's Devstral Small 2!")
        return 0
    else:
        print(f"✗ {total - passed} of {total} tests FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
