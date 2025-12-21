# Hybrid Testing Agent Design

## Overview
The testing agent should be a **hybrid** of Agent 1 (implementer) and Agent 2 (reviewer). Unlike the regular reviewer, it can both review AND take action by writing and running tests itself.

## Current State
- Testing agent exists as `agent2_testing`
- Currently switches based on completeness threshold
- Acts like a pure reviewer (no tools for implementation)
- Uses parsing for instructions instead of tool submission

## Proposed Design

### 1. Trigger Mechanism
**Every 3 cycles** instead of threshold-based:
```python
# In orchestrator
if cycle_count % 3 == 0:
    use_testing_agent = True
else:
    use_testing_agent = False
```

This ensures regular testing focus regardless of completeness score.

### 2. Hybrid Capabilities

The testing agent is **BOTH** a reviewer and implementer:

**As Reviewer (like Agent 2):**
- Reviews test suite quality
- Identifies missing tests
- Checks test coverage
- Submits instructions via `submit_next_instructions()` tool

**As Implementer (like Agent 1):**
- Has access to ALL Agent 1 tools:
  - `file_write` - can write test files directly
  - `file_read` - can read code to understand what to test
  - `bash` - can run test commands
  - `search_content` - can find untested code
  - `git_commit` - can commit test improvements

**Unique workflow:**
1. Review codebase and existing tests
2. Identify testing gaps
3. **WRITE the missing tests itself** (not just tell Agent 1 to do it)
4. **RUN the tests** to verify they work
5. Submit refined instructions to Agent 1 for any implementation fixes needed
6. Save testing patterns to memory

### 3. Tool Access

Testing agent needs a special ToolRegistry:
```python
# In orchestrator.py
self.testing_agent_tools = ToolRegistry(workspace, agent_name="agent_testing")
```

This registry should have:
- All Agent 1 implementation tools (file_write, bash, etc.)
- Agent 2 review tools (submit_next_instructions, memory_write)
- Hybrid capabilities!

### 4. System Prompt

The testing agent prompt should emphasize:

```
You are the Testing Agent: A HYBRID reviewer + implementer.

YOUR UNIQUE POWER: You can WRITE and RUN tests yourself!

WORKFLOW:
1. Review what tests exist
2. Identify what's missing
3. WRITE the test files yourself using file_write()
4. RUN the tests using bash("pytest ...")
5. Fix any issues in YOUR tests
6. Submit instructions to Agent 1 for implementation fixes (if needed)
7. Save testing observations to memory

DON'T just tell Agent 1 "write tests" - YOU write them!

GOOD:
- file_write("tests/test_auth.py", "def test_login()...")
- bash("pytest tests/test_auth.py -v")
- If tests fail due to implementation bug, submit_next_instructions() for Agent 1

BAD:
- "Agent 1 should write tests..." (NO! YOU write them!)
- Reviewing without running tests
- Telling instead of doing
```

### 5. Agent Class Design

Option A: Create new `AgentTesting` class that inherits from both behaviors
```python
class AgentTesting:
    def __init__(self, llm, system_prompt, tools):
        self.llm = llm
        self.system_prompt = system_prompt
        self.tools = tools  # Full tool access

    def test_and_review(self, spec, codebase, git_log):
        # Like Agent1.run() but focused on testing
        # Has iteration loop to write/run tests
        # Can also submit_next_instructions like Agent2
```

Option B: Use Agent1 class with testing-specific prompt and tools
```python
# Simpler approach
self.agent_testing = Agent1(
    llm=self.llm,
    tools=self.testing_agent_tools,  # Hybrid tools
    system_prompt=TESTING_AGENT_PROMPT,
    max_iterations=30  # More iterations for test writing
)
```

### 6. Orchestrator Integration

```python
def _run_cycle(self):
    cycle_num = self.state.cycle_count + 1

    # Agent 1 implementation
    agent1_response = self.agent1.run(...)

    # Decide which reviewer to use
    if cycle_num % 3 == 0:
        # Every 3rd cycle: Testing agent (hybrid)
        review = self.agent_testing.test_and_review(...)
        self.state.phase = "testing"
    else:
        # Normal cycles: Regular reviewer
        review = self.agent2_implementation.review(...)
        self.state.phase = "implementation"
```

### 7. Benefits

**More Effective Testing:**
- Testing agent directly writes quality tests instead of instructing Agent 1
- Tests are written by an agent focused solely on testing
- Agent 1 can focus on implementation, not test writing

**Faster Iteration:**
- No back-and-forth: "write tests" → Agent 1 writes bad tests → "fix tests"
- Testing agent writes them right the first time

**Better Test Quality:**
- Testing agent runs tests immediately and verifies they work
- Can iterate on test improvements in same cycle
- Agent 1 only gets instructions for implementation bugs, not test bugs

**Clear Separation:**
- Agent 1: Implementation
- Agent 2: Code review & direction
- Testing Agent: Test implementation & test review

### 8. Example Cycle Flow

```
Cycle 1: Agent 1 implements feature → Agent 2 reviews → Instructions for next feature
Cycle 2: Agent 1 continues → Agent 2 reviews → More instructions
Cycle 3: Agent 1 continues → TESTING AGENT activates
  → Testing agent reviews tests
  → Finds gaps in error handling tests
  → WRITES file tests/test_error_handling.py directly
  → RUNS bash("pytest tests/test_error_handling.py")
  → Tests pass!
  → Finds implementation bug revealed by tests
  → submit_next_instructions("Fix the ValueError in auth.py:45...")
  → Saves to memory: "Agent 1 often forgets ValueError checks"
Cycle 4: Agent 1 fixes bug → Agent 2 reviews → Continue...
```

## Implementation Checklist

- [ ] Create hybrid ToolRegistry for testing agent
- [ ] Write TESTING_AGENT_PROMPT (hybrid behavior)
- [ ] Change trigger from threshold to every-3-cycles
- [ ] Decide on AgentTesting class vs reuse Agent1
- [ ] Update orchestrator to pass full tools to testing agent
- [ ] Test that testing agent can write AND review
- [ ] Ensure testing agent appears in "Wrapped" stats separately
- [ ] Update CLI to show "testing" phase differently

## Open Questions

1. Should testing agent have its own memory file (AGENT_TESTING_MEMORY.md)?
2. How to prevent testing agent from modifying implementation code (only test code)?
3. Should testing agent commit its test changes directly, or leave for Agent 1?
4. What if testing agent's tests reveal critical bugs - should it interrupt the 3-cycle pattern?
