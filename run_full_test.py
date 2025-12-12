#!/usr/bin/env python3
"""
Full end-to-end test of the completeness loop with Mistral backend.
This runs Agent 1 (implementation) and Agent 2 (review) through complete cycles.
"""

import os
import sys
from pathlib import Path

# Set API key
os.environ["MISTRAL_API_KEY"] = "5H33wYE5mr0ZgEE7xw0cRJ4bWP8QT0qQ"

sys.path.insert(0, str(Path(__file__).parent))

from src.config import LoopConfig
from src.orchestrator import Orchestrator

def main():
    # Setup
    base_dir = Path(__file__).parent
    spec_file = base_dir / "test-spec.md"
    workspace = base_dir / "workspace"

    if not spec_file.exists():
        print(f"Error: {spec_file} not found")
        return 1

    workspace.mkdir(exist_ok=True)

    # Copy spec to workspace
    idea_file = workspace / "idea.md"
    idea_file.write_text(spec_file.read_text())

    # Load config
    config = LoopConfig()
    config.limits.max_iterations = 3  # Just 3 cycles for testing

    print("╔" + "=" * 70 + "╗")
    print("║" + " " * 70 + "║")
    print("║" + "  AUTONOMOUS AGENT LOOP - END-TO-END TEST".center(70) + "║")
    print("║" + " " * 70 + "║")
    print("╚" + "=" * 70 + "╝")
    print()

    print(f"Spec: Task Manager CLI Application")
    print(f"Backend: {config.model.backend} ({config.model.name})")
    print(f"Max cycles: {config.limits.max_iterations}")
    print()
    print("=" * 70)
    print()

    # Create orchestrator
    orchestrator = Orchestrator(
        workspace=workspace,
        idea_file=idea_file,
        config=config,
        on_status_change=lambda msg: print(f"  {msg}"),
        on_cycle_complete=print_cycle_result
    )

    # Run the loop
    print("Starting autonomous loop...\n")
    state = orchestrator.run(resume=False)

    # Print final summary
    print()
    print("=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Cycles completed: {state.cycle_count}")
    print(f"Final completeness: {state.completeness_history[-1]['score'] if state.completeness_history else 0}%")
    print(f"Agent 1 tokens: {state.total_agent1_usage.total_tokens:,}")
    print(f"Agent 2 tokens: {state.total_agent2_usage.total_tokens:,}")
    print(f"Total tokens: {state.total_agent1_usage.total_tokens + state.total_agent2_usage.total_tokens:,}")
    print()

    # List files created
    print("Files created in workspace:")
    for f in sorted(workspace.glob("*")):
        if not f.name.startswith("."):
            size = f.stat().st_size if f.is_file() else "dir"
            print(f"  - {f.name} ({size})")

    print()
    return 0

def print_cycle_result(result):
    """Print cycle result."""
    print()
    print(f"  Cycle {result.cycle_number}: Score {result.completeness_score}% ({result.duration_seconds:.1f}s)")
    if result.agent1_response:
        print(f"    Agent 1: {result.agent1_response.usage.total_tokens:,} tokens, {result.agent1_response.iterations} iterations")
    if result.agent2_review:
        print(f"    Agent 2: {result.agent2_review.usage.total_tokens:,} tokens")
        if result.agent2_review.remaining_work:
            for item in result.agent2_review.remaining_work[:2]:
                print(f"      • {item[:60]}")

if __name__ == "__main__":
    sys.exit(main())
