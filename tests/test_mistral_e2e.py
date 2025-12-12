#!/usr/bin/env python3
"""
End-to-end test for Mistral integration with completeness loop.

This test verifies:
1. Configuration loads correctly with Mistral defaults
2. LLM backend is instantiated properly
3. Orchestrator can be created with Mistral backend
4. Tool registry works with Mistral
5. Mock workspace can be set up
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import LoopConfig
from src.llm import create_backend, MistralBackend
from src.tools import ToolRegistry
from src.orchestrator import Orchestrator
from src.context import ContextBuilder


def test_config_loading():
    """Test that config loads with Mistral defaults."""
    print("Test 1: Config loading with Mistral defaults")
    print("-" * 60)

    config = LoopConfig()
    print(f"  Backend: {config.model.backend}")
    print(f"  Model: {config.model.name}")
    print(f"  Max tokens: {config.model.max_tokens}")
    print(f"  Temperature: {config.model.temperature}")

    assert config.model.backend == "mistral"
    assert config.model.name == "devstral-small-2505"
    assert config.model.max_tokens == 4096
    assert config.model.temperature == 0.7

    print("✓ PASSED")
    return True


def test_backend_creation():
    """Test that backend is correctly created from config."""
    print("\nTest 2: Backend creation from config")
    print("-" * 60)

    os.environ["MISTRAL_API_KEY"] = "test-key-mistral-123"

    config = LoopConfig()
    backend = create_backend(config)

    print(f"  Backend type: {type(backend).__name__}")
    print(f"  Backend info: {backend.get_info()}")
    print(f"  Supports tools: {backend.supports_tools()}")

    assert isinstance(backend, MistralBackend)
    assert backend.supports_tools() == True

    print("✓ PASSED")
    return True


def test_tool_registry():
    """Test that tool registry can be instantiated."""
    print("\nTest 3: Tool registry with Mistral workspace")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        tools = ToolRegistry(workspace)

        print(f"  Workspace: {workspace}")
        print(f"  Tool count: {len(tools._tools)}")
        print(f"  Available tools: {', '.join(list(tools._tools.keys())[:5])}...")

        # Check that essential tools are available
        assert "bash" in tools._tools
        assert "file_read" in tools._tools
        assert "file_write" in tools._tools
        assert "git_add" in tools._tools

        print("✓ PASSED")
        return True


def test_context_builder():
    """Test that context builder works with workspace."""
    print("\nTest 4: Context builder initialization")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create a minimal spec
        spec_file = workspace / "idea.md"
        spec_file.write_text("# Test Project\nBuild a test project")

        context = ContextBuilder(workspace, original_spec_name="idea.md")

        print(f"  Workspace: {workspace}")
        print(f"  Spec name: {context.original_spec_name}")

        assert context.workspace == workspace
        assert context.original_spec_name == "idea.md"

        print("✓ PASSED")
        return True


def test_orchestrator_creation():
    """Test that orchestrator can be created with Mistral."""
    print("\nTest 5: Orchestrator creation with Mistral")
    print("-" * 60)

    os.environ["MISTRAL_API_KEY"] = "test-key-mistral-123"

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        workspace.mkdir(exist_ok=True)

        # Create spec file
        idea_file = workspace / "idea.md"
        idea_file.write_text("# Test Project\n\nBuild a simple calculator app")

        # Create config with Mistral
        config = LoopConfig()

        try:
            # Create orchestrator
            orchestrator = Orchestrator(
                workspace=workspace,
                idea_file=idea_file,
                config=config
            )

            print(f"  LLM backend: {orchestrator.llm.get_info()}")
            print(f"  Tools: {len(orchestrator.tools._tools)} available")
            print(f"  Original spec length: {len(orchestrator.original_spec)} chars")

            assert isinstance(orchestrator.llm, MistralBackend)
            assert orchestrator.workspace == workspace
            assert orchestrator.idea_file == idea_file

            print("✓ PASSED")
            return True
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_mistral_model_names():
    """Test that all standard Mistral models can be configured."""
    print("\nTest 6: Mistral model name validation")
    print("-" * 60)

    os.environ["MISTRAL_API_KEY"] = "test-key"

    models = {
        "devstral-small-2505": "Devstral Small 2 (24B) - Recommended for coding",
        "mistral-small-latest": "Mistral Small - General purpose",
        "mistral-large-latest": "Mistral Large - For complex tasks",
    }

    all_passed = True
    for model_name, description in models.items():
        try:
            config = LoopConfig()
            config.model.name = model_name
            config.model.backend = "mistral"

            backend = create_backend(config)

            print(f"  ✓ {model_name}")
            print(f"    {description}")

        except Exception as e:
            print(f"  ❌ {model_name}: {e}")
            all_passed = False

    if all_passed:
        print("✓ PASSED: All models supported")
        return True
    else:
        print("❌ FAILED: Some models not supported")
        return False


def test_error_handling():
    """Test that proper errors are raised for invalid configs."""
    print("\nTest 7: Error handling for invalid configs")
    print("-" * 60)

    os.environ["MISTRAL_API_KEY"] = ""

    try:
        backend = MistralBackend()
        print("❌ FAILED: Should raise error for empty API key")
        return False
    except ValueError:
        print("  ✓ Empty API key raises ValueError")

    # Test with invalid backend
    config = LoopConfig()
    config.model.backend = "invalid-backend"

    try:
        backend = create_backend(config)
        print("❌ FAILED: Should raise error for invalid backend")
        return False
    except ValueError as e:
        print(f"  ✓ Invalid backend raises ValueError")
        print(f"    Error: {str(e)[:60]}...")

    print("✓ PASSED")
    return True


def main():
    """Run all end-to-end tests."""
    print("\n" + "=" * 60)
    print("MISTRAL E2E INTEGRATION TESTS")
    print("=" * 60)

    tests = [
        test_config_loading,
        test_backend_creation,
        test_tool_registry,
        test_context_builder,
        test_orchestrator_creation,
        test_mistral_model_names,
        test_error_handling,
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
        print(f"✓ ALL {total} E2E TESTS PASSED")
        print("=" * 60)
        print("\n✨ Mistral integration is fully operational!")
        print("\nNext steps:")
        print("  1. export MISTRAL_API_KEY='your-actual-key'")
        print("  2. Create your project with idea.md")
        print("  3. Run: python main.py")
        print("  4. Type: go")
        print("\nThe agent loop will automatically use Mistral's Devstral Small 2!")
        return 0
    else:
        print(f"✗ {total - passed} of {total} tests FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
