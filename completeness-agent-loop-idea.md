# Completeness Agent Loop

## Project Overview

An autonomous multi-agent system that completes long, complex coding tasks overnight by using a review-loop pattern with automatic git backups. The system runs locally using a lightweight LLM (Devstral small 2) in a sandboxed VM environment, allowing it to work independently without human intervention until morning.

## Core Problem Being Solved

### The "Giving Up" Problem

Devstral small 2 achieves 60% on SWE-bench verified, demonstrating strong coding capability. However, in interactive use it exhibits premature stopping:

**Typical Single-Agent Pattern:**
```
Human: "Implement feature X with A, B, and C"
Agent: [implements A and part of B]
Agent: "I've implemented the feature with A and B functionality"
Human: "But you didn't do C, and B is incomplete"
Agent: [implements a bit more of B, still skips C]
Agent: "Updated the implementation"
Human: "Still missing C..."
```

This requires constant human intervention to push for completeness. For overnight tasks, this doesn't work—no one to send "continue" messages.

### The Self-Assessment Bias Problem

Adding a second agent helps, but if Agent 2 sees Agent 1's self-assessment, same-model bias creates a new failure mode:

**Bad: Agent 2 sees Agent 1's response:**
```
Agent 1: [implements partial solution]
Agent 1: "I've fully implemented error handling for all edge cases and 
         the solution is production-ready with comprehensive validation."

Agent 2 sees: Confident summary + partial code
Agent 2 thinks: "Sounds complete, the summary says all edge cases are covered"
Agent 2: "Great work! Moving on to next feature..."

Result: Agent 2 was persuaded by Agent 1's framing, didn't check actual code
```

**Good: Agent 2 sees only code:**
```
Agent 1: [implements partial solution]
Agent 1: "I've fully implemented..." [discarded, never sent to Agent 2]

Agent 2 sees: Only the code + spec
Agent 2 checks: 
- Spec requires: null handling, type validation, range checking, network errors
- Code has: one try/except block catching generic Exception
Agent 2: "Error handling incomplete. Missing: null checks, type validation, 
         range checking, specific network error handling. Implement these now."

Result: Objective gap analysis based on code vs. spec
```

### The Completeness Loop Solution

By adding Agent 2 as a persistence layer that reviews only code:

**Multi-Agent Pattern:**
```
Cycle 1: Agent 1 implements A and part of B, stops
Cycle 2: Agent 2 (code-only review): "Missing B completion and C. Continue with: [specific steps]"
Cycle 3: Agent 1 completes B, partially does C, stops
Cycle 4: Agent 2 (code-only review): "C is incomplete. Specifically you need: [details]"  
Cycle 5: Agent 1 finishes C
Cycle 6: Agent 2 (code-only review): "Now complete! Moving to tests..."
```

Agent 2 provides the persistence that Agent 1 lacks, judged purely from code against spec. The system reaches 100% completion without human intervention, even though Agent 1 stops multiple times along the way.

**Key Insight:** It's not about Agent 1 being incapable—it can do the work. It's about (1) external motivation to finish what it starts, and (2) objective review that isn't influenced by Agent 1's self-assessment. Agent 2 provides both.

## Core Architecture

### Two-Agent System

**Agent 1 (Implementation Agent)** - Fresh context each cycle
- Receives: Current codebase + Agent 2's instructions + last commit message
- Implements code, creates files, runs commands, runs tests
- Executes git commits when instructed by Agent 2
- Has full access to development tools and internet
- Works within the sandboxed VM
- **Key trait**: Capable but gives up easily on hard tasks

**Agent 2 (Persistence & Review Agent)** - Fresh context each cycle
- Always starts with fresh context
- Always receives: Original idea.md + current codebase
- Reviews codebase against requirements
- Rates completeness (0-100%)
- Generates detailed, specific continuation prompts for Agent 1
- Instructs Agent 1 to commit with appropriate messages
- Lists remaining tasks and gaps
- **Key trait**: Never accepts "good enough"—enforces persistence
- Prevents project drift by maintaining reference to original spec

### Workflow Loop

```
1. Agent 1 receives: codebase + Agent 2's instructions (or initial idea.md)
2. Agent 1 implements features, commits when instructed
   └─> Agent 1's response/summary is discarded (NOT sent to Agent 2)
3. Agent 2 receives: original idea.md + updated codebase + git log
   └─> Agent 2 reviews ONLY the code, not Agent 1's explanations
4. Agent 2 reviews completeness and generates next instructions
5. If incomplete: goto step 1
6. If complete but no tests: Agent 2 focuses on testing requirements
7. If tests incomplete/failing: Agent 2 persists until tests pass
8. If complete with passing tests: project done
```

**Key architectural decision:** Agent 1's response text never reaches Agent 2. Only the code changes. This prevents same-model bias where Agent 2 might be persuaded by Agent 1's confident-but-wrong self-assessments.

### The Persistence Pattern

The loop solves Devstral small 2's tendency to give up:

```
Cycle N:   Agent 1 attempts task, gets 60% done, gives up
Cycle N+1: Agent 2 notices incompleteness, writes specific continuation
Cycle N+2: Agent 1 continues, gets to 80%, gives up again
Cycle N+3: Agent 2 identifies remaining 20%, gives detailed steps
Cycle N+4: Agent 1 finishes the task

Without the loop: Stuck at 60%
With the loop: Eventually reaches 100%
```

Agent 2 acts as an external persistence layer that compensates for Agent 1's premature stopping.

## Technical Requirements

### Context Refresh Strategy

Both agents get fresh context each cycle to prevent error accumulation:

**Agent 1 Context Package:**
```
SYSTEM: [Implementation agent instructions]

CODEBASE SNAPSHOT:
├── Current file tree
└── Full contents of key files (based on Agent 2's focus areas)

LAST COMMIT:
[Previous git commit message - shows what was just accomplished]

INSTRUCTIONS:
[Agent 2's detailed next steps, including commit instructions]

TASK CONTEXT:
[One-paragraph summary of overall goal from idea.md]
```

**Agent 2 Context Package:**
```
SYSTEM: [Review agent instructions emphasizing persistence]

ORIGINAL SPECIFICATION:
[Complete idea.md file]

CURRENT CODEBASE:
├── Complete file tree
├── All source files
├── Test files
└── Git log (last 5 commits)

YOUR TASK:
Review completeness, rate progress, generate next specific instructions
Remember: Do not accept premature stopping. Push for full implementation.

CRITICAL: You are reviewing ONLY the code against the specification.
Do NOT see Agent 1's explanations, summaries, or self-assessments.
Judge completeness purely from what exists in the codebase.
```

**What Agent 2 NEVER sees:**
- Agent 1's response text or reasoning
- Agent 1's self-assessment of completion
- Agent 1's explanations of implementation choices
- Agent 1's statements about what's "done" or "complete"

This prevents Agent 2 from being influenced by Agent 1's potentially over-confident or avoidant framing. Agent 1 might say "comprehensive error handling implemented" when only 2 of 5 error cases are handled. Agent 2 must judge from the code itself.

This approach means:
- No conversation history to get polluted
- Each cycle is a "fresh start" with clear context
- Git log serves as the only persistent state
- Agents can't accumulate bad assumptions

**Preventing Agent 1 from "Gaming" Agent 2:**

Fresh context for Agent 1 means it can't learn patterns like:
- "If I create a function stub, Agent 2 thinks I'm done"
- "Agent 2 doesn't check if tests actually run"
- "Agent 2 accepts incomplete error handling"

Each cycle, Agent 1 approaches the task freshly based on Agent 2's explicit instructions. It can't develop shortcuts because it has no memory of previous cycles—only the codebase state and current instructions.

**Critical: Preventing Self-Assessment Bias**

Agent 2 must NEVER see Agent 1's response text, explanations, or self-assessments. Only the code.

**Why this matters:**

Agent 1's summaries often reveal avoidance through what they emphasize:
```
Agent 1: "I've implemented the feature with comprehensive error handling 
         and all edge cases covered. The solution is complete and robust."
         
Actual code: try:
                 process(data)
             except:
                 pass  # Only catches generic exceptions, no specific handling
```

If Agent 2 (same model) sees Agent 1's confident summary, it might be persuaded. Same model = same blind spots and reasoning patterns. Agent 1 saying "it's complete" might convince Agent 2 to stop pushing, even when the code clearly isn't complete.

**Solution:** Agent 2 reviews purely code vs. spec. No intermediary framing. This forces objective assessment:
- Does error handling cover the specific cases in idea.md? (No)
- Do tests exist for each requirement? (No)
- Is the implementation actually complete? (No)

Agent 2 generates the next instruction based purely on gap analysis, not influenced by Agent 1's framing of the gaps.

### Environment

- **VM Sandbox**: Isolated Linux VM (lightweight)
- **RAM Allocation**: ~8GB for VM (main system runs 24B model with ~24GB)
- **Model**: Devstral small 2 (24B) running locally via MLX
- **Cost**: Zero (fully local execution)
- **Runtime**: Overnight (8-12 hours typical)

### CLI Interface

Must provide:
- Real-time agent activity display
- Token usage tracking (per agent, cumulative)
- Current phase indicator (implementation/review/testing)
- Progress percentage from Agent 2
- Commit history viewer
- Ability to pause/resume
- Log file generation

### Tool Requirements

Agent 1 must have access to:
- **File Operations**: create, read, write, delete, move, copy
- **Code Editing**: full text editing, search/replace
- **Command Execution**: bash, python, node, etc.
- **Jupyter Notebooks**: create, edit cells, execute
- **Package Management**: pip, npm, apt, etc.
- **Internet Access**: unrestricted (in sandbox)
- **Git Operations**: via Agent 3 coordination
- **Testing Frameworks**: pytest, jest, unittest, etc.
- **Build Tools**: make, cmake, cargo, etc.
- **Database Tools**: sqlite, postgres client, etc.
- **Network Tools**: curl, wget, nc, etc.

Comprehensive tool list (examples):
- bash execution
- file_create, file_read, file_write, file_delete
- str_replace_editor
- jupyter_create, jupyter_edit_cell, jupyter_execute
- search_files, find_in_files
- list_directory, tree_view
- run_tests, check_syntax
- install_package, run_command
- http_request, download_file

## Implementation Specifications

### System Architecture Enforcement

The loop controller must **actively discard** Agent 1's response text:

```python
# CORRECT: Agent 1 output never reaches Agent 2
agent1_response = run_agent1(instructions)
commit_result = execute_git_commit(agent1_response)  # Extract commit command if needed
# agent1_response is now discarded
updated_codebase = read_codebase()
agent2_instructions = run_agent2(idea_md, updated_codebase, git_log)

# WRONG: This would allow bias
agent2_instructions = run_agent2(idea_md, codebase, git_log, agent1_response)  # NO!
```

This isn't just a guideline—it must be architecturally impossible for Agent 2 to see Agent 1's explanations. The system should literally not pass that data.

**What Agent 1 outputs (for loop controller only):**
- Git commands to execute
- Code changes made
- Files created/modified
- Optional: debugging info for human morning review

**What Agent 2 receives:**
- Only filesystem state (codebase)
- Git log (factual commit history)
- Original spec

The air gap between Agent 1's self-assessment and Agent 2's review is critical to preventing same-model persuasion.

### The Testing Persistence Challenge

Testing will likely require the most cycles due to the giving-up problem:

**Expected Testing Pattern:**
```
Cycle 10: Agent 2: "Implementation complete at 70%. Now write comprehensive tests."
Cycle 11: Agent 1 writes 3 basic happy-path tests, stops
Cycle 12: Agent 2: "Only 3 tests. Need edge cases, error handling, integration tests."
Cycle 13: Agent 1 adds 2 edge case tests, stops
Cycle 14: Agent 2: "Still missing: error handling tests, boundary condition tests..."
Cycle 15: Agent 1 adds 2 more tests, stops  
Cycle 16: Agent 2: "Now have 7 tests but missing: [specific scenarios]..."
... (continues 5-10 more cycles)
Cycle 24: Agent 2: "Test suite complete at 95%. Run the tests."
Cycle 25: Agent 1 runs tests, 2 fail
Cycle 26: Agent 2: "Tests failing in test_edge_case.py. Fix the implementation..."
```

**This is fine for overnight execution.** If comprehensive testing takes 15-20 cycles, that's acceptable. The alternative—incomplete tests—defeats the purpose of automated development.

**Agent 2's testing persistence strategy:**
- Enumerate specific test cases that must exist
- Check that tests actually run (not just exist)
- Verify test coverage of core functionality
- Confirm tests actually assert meaningful behavior
- Don't move to "complete" until tests pass

### Agent 2 Review Format

Agent 2 must always output structured reviews with commit instructions:

```markdown
## Completeness Score: X/100

## What Was Just Completed:
- Feature A: Fully implemented in commit abc123
- Feature B: Partially done (missing error handling)

## Remaining Work (Priority Order):
1. Add error handling to feature B (files: b.py, lines 40-60)
2. Implement feature C (create new file c.py)
3. Write tests for features A and B (test_a.py, test_b.py)
4. Add documentation to README

## Specific Issues Found:
- b.py line 42: Missing null check
- a.py: Function `process_data` needs type hints
- No test coverage for edge cases

## Commit Instructions:
```bash
git add [files to add]
git commit -m "[Component] Brief description

- Specific changes
- Files affected

Completeness: X/100"
```

## Next Instructions for Agent 1:
Start by committing your current work with the message above.

Then, focus on the highest priority item: [specific detailed instructions]
Remember to handle [specific edge case] and test [specific scenario].

When done, check that [specific validation criteria].

DO NOT MOVE ON until this is complete. Even if it seems hard, persist.
```

The key is making instructions:
- **Specific**: Exact files, line numbers, function names
- **Actionable**: Clear next steps, not vague goals
- **Testable**: How Agent 1 will know it's done
- **Persistent**: Explicit instruction not to give up

### Git Commit Strategy

Commits happen after each Agent 1 cycle, instructed by Agent 2:

**Commit message format (specified by Agent 2):**
```
[Component/Feature] Brief description

- Specific changes made
- Files affected or added
- Known issues if any

Completeness: X/100
Status: [Implementation/Testing/Fixing/Complete]
```

**Note on commit message bias:** Commit messages are written by Agent 1 but read by Agent 2, creating a potential bias vector. Agent 1 might write "Fully implemented comprehensive error handling" when only basic error handling exists.

**Mitigation options:**
1. **Loop controller sanitization:** Rewrite commit messages to be purely factual (list of files changed, functions added)
2. **Agent 2 instruction:** Teach Agent 2 to ignore commit message claims and verify against code
3. **Structured commits:** Agent 2 specifies exact commit message format, Agent 1 just fills in blanks

For MVP, option 2 (teach Agent 2 to verify) is simplest. Include in Agent 2's system prompt: "Commit messages may contain Agent 1's self-assessments. Do not trust claims of completeness—verify everything against the actual code."

**Example commits in a typical sequence:**
```
[Core] Initial project structure

- Created main.py, config.py, utils.py
- Set up basic CLI argument parsing

Completeness: 15/100
Status: Implementation
---
[Core] Add data processing pipeline

- Implemented DataProcessor class
- Added input validation
- Missing error handling (noted for next cycle)

Completeness: 35/100
Status: Implementation
---
[Core] Add error handling and edge cases

- Added try-catch blocks to process_data
- Handle empty input, malformed data
- Fixed bug from previous commit

Completeness: 50/100
Status: Implementation
---
[Tests] Initial test suite

- Created test_data_processor.py
- Basic happy path tests only
- Need edge case tests

Completeness: 65/100
Status: Testing
```

Each commit creates a checkpoint that:
- Shows incremental progress
- Allows rollback if needed
- Provides project history for morning review
- Tracks completeness over time

### Error Handling

- **Agent 1 errors**: Logged, Agent 2 reviews, generates fix prompt
- **Agent 3 git errors**: Attempts resolution, logs if unfixable, continues
- **VM crashes**: Auto-restart with state recovery
- **Model inference errors**: Retry with backoff, log if persistent
- **Infinite loops**: Max iteration limit (configurable, default 50 cycles)

## Safety & Constraints

### Sandbox Requirements
- Full VM isolation from host system
- No access to host filesystem
- Network isolated (except internet)
- Resource limits enforced (CPU, memory, disk)
- Easy to reset/rebuild

### Agent Constraints
- **Agent 1**: Can do anything in the sandbox, including git commits
- **Agent 2**: Cannot execute code or modify files directly, only review and instruct
- **Both agents**: Cannot access host system
- **Both agents**: Cannot modify core loop logic  
- **Both agents**: Get fresh context each cycle (no conversation memory)
- **Agent 2**: Must push for persistence—cannot accept incomplete work
- **Max runtime**: Configurable cutoff (default 12 hours)
- **Max cycles**: Configurable limit (default 100 cycles)

## Success Criteria

A completed run should produce:
1. Codebase matching idea.md specifications
2. Comprehensive test suite with passing tests
3. Clean git history showing incremental progress
4. Documentation for implemented features
5. Agent 2 final review scoring 95%+ completeness
6. Morning-readable logs showing agent reasoning

## Configuration File Format

```yaml
completeness_loop_config:
  model:
    name: "devstral-small-2"
    max_tokens: 4096
    temperature: 0.7
  
  vm:
    ram_gb: 8
    disk_gb: 50
    os: "ubuntu-22.04"
    
  limits:
    max_iterations: 50
    max_runtime_hours: 12
    max_commits: 200
    
  agents:
    agent1_system_prompt: "path/to/implementer.txt"
    agent2_system_prompt: "path/to/reviewer.txt"
    agent1_context_token_limit: 32000  # How much codebase to include
    agent2_context_token_limit: 32000  # Usually needs full codebase
    
  tools:
    - bash_execution
    - file_operations
    - jupyter_tools
    - [... full list]
    
  monitoring:
    log_level: "INFO"
    token_tracking: true
    save_screenshots: false
```

## Example Usage

```bash
# Start a new task
completeness-loop start --idea ./my-project-idea.md --workspace ./sandbox-ws

# Resume interrupted task
completeness-loop resume --workspace ./sandbox-ws

# Monitor running task
completeness-loop status

# View agent conversation
completeness-loop logs --tail 50

# Check completion score
completeness-loop score
```

## Future Enhancements

- Multi-project parallelization
- Human-in-the-loop checkpoints (optional)
- Agent 4: Documentation specialist
- Integration with Claude Code for smarter coding
- Support for larger models when RAM allows
- Web UI for monitoring
- Slack/Discord notifications when complete
- Comparative runs (try multiple approaches)

## Non-Goals

- Real-time human interaction (designed for overnight)
- Production deployment (sandbox only)
- Multi-machine coordination (single machine for now)
- Handling private/sensitive codebases (everything in sandbox)

## Open Questions

1. **Context window management:** At what point does the codebase become too large to fit in Agent 2's context? Need strategies for large projects (maybe selective file inclusion based on Agent 2's focus areas).

2. **Agent 2 prompt calibration:** How detailed should Agent 2's instructions be? Too vague → Agent 1 gives up. Too specific → Agent 1 becomes a puppet (might not need to be smart).

3. **Detecting genuine impossibility:** How does Agent 2 distinguish between "Agent 1 gave up too early" vs "this task is actually impossible/underspecified"? Cycle count threshold? Explicit Agent 1 error signals?

4. **Optimal cycle length:** Should Agent 1 work for X tokens/minutes before Agent 2 reviews? Or always review after each "natural stopping point" (commit)?

5. **Test-driven development:** Should Agent 2 push for tests-first methodology, or implementation-first? Which works better with Devstral small 2's behavior?

6. **Partial credit for tests:** If Agent 1 writes tests that exist but don't actually test anything meaningful (assert True), how does Agent 2 detect this? Need test quality evaluation, not just existence.

7. **Commit granularity:** Should there be multiple commits per Agent 1 cycle for complex tasks, or always one commit per cycle? Trade-off between git history detail vs added complexity.

8. **Model size experiment:** Would Devstral large 2 or Qwen2.5-Coder-32B as Agent 2 provide better persistence enforcement, even if Agent 1 stays small?

9. **Commit message contamination:** Git commit messages are written by Agent 1 and seen by Agent 2. Could Agent 1's self-assessment leak through commit messages? (e.g., "Fully implemented all error handling" when incomplete). Should the loop controller sanitize/rewrite commit messages to be purely factual?

10. **stderr/stdout capture:** When Agent 1 runs tests or commands, should Agent 2 see the output? This could help with debugging but might also contain Agent 1's interpretations that bias Agent 2.

## Success Metrics

- **Completion Rate**: % of tasks that reach 95%+ by morning
- **Code Quality**: Tests passing, linting clean
- **Efficiency**: Average tokens per feature implemented
- **Stability**: VM crashes per 100 runs
- **Usefulness**: Human intervention required to finish project

## Technical Dependencies

- Python 3.11+
- MLX framework for local inference
- Git 2.40+
- Docker or QEMU for VM
- ~50GB disk space for VM and model
- Apple Silicon Mac (for MLX) or CUDA GPU alternative

## Timeline Estimate

- Core loop implementation: 1 week
- Agent prompt engineering: 3 days
- Tool integration: 1 week  
- VM/sandbox setup: 3 days
- CLI interface: 3 days
- Testing & refinement: 1 week

**Total: ~1 month for MVP**

## Notes

- This is optimized for the "give it a task Friday night, review Saturday morning" workflow
- The fresh context for Agent 2 is crucial—prevents accumulated errors/drift
- Git history becomes the project's "memory"—shows reasoning through commits
- The sandbox isn't just for safety—it's for freedom (agents can experiment)
- Token cost being zero enables long, exploratory development overnight
