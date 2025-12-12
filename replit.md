# Completeness Agent Loop

## Overview
An autonomous multi-agent CLI system that completes complex coding tasks overnight using a review-loop pattern with automatic git backups. Uses local LLM inference (Devstral Small 2 via MLX/Ollama/LM Studio) to run independently without human intervention.

## Architecture

### Two-Agent System
- **Agent 1 (Implementation)**: Receives instructions, implements code, runs tests, makes commits
- **Agent 2 (Review/Persistence)**: Reviews codebase against spec, rates completeness (0-100%), generates next instructions

### Dual Agent 2 Prompts
Agent 2 uses different system prompts depending on the phase:
- **Implementation Phase** (score < 70%): Reviews codebase, assigns implementation tasks
- **Testing Phase** (score >= 70%): Reviews test suite, assigns testing tasks

### Key Design Decision
Agent 2 NEVER sees Agent 1's self-assessments or explanations - only the code. This prevents same-model bias where Agent 2 might be persuaded by Agent 1's confident-but-wrong summaries.

## Project Structure
```
src/
├── __init__.py       # Package init
├── config.py         # Configuration with Pydantic models
├── llm.py            # LLM backends (Ollama, LM Studio, MLX, HTTP)
├── tools.py          # Tool registry for Agent 1 (bash, files, git)
├── agents.py         # Agent 1 and Agent 2 implementations
├── context.py        # Context building for agent prompts
├── orchestrator.py   # Main loop controller with phase transitions
└── cli.py            # ASCII CLI interface (scrolling output)
prompts/
├── agent1_system.txt         # Agent 1 system prompt
├── agent2_implementation.txt # Agent 2 implementation review prompt
└── agent2_testing.txt        # Agent 2 testing review prompt
main.py               # Entry point
```

## Usage

### Quick Start (Zero-Config)
```bash
# 1. Create a folder with your project idea
mkdir my-project && cd my-project

# 2. Write your specification
cat > idea.md << 'EOF'
# My Todo App
Build a command-line todo list manager with:
- Add, remove, complete tasks
- Save to JSON file
- List all tasks with status
EOF

# 3. Run the agent
python /path/to/completeness-loop/main.py

# 4. Type 'go' and watch it build!
```

### Interactive Commands
```
❯ go          Start building (auto-detects idea.md, sets up workspace + git)
❯ resume      Resume a paused session
❯ status      Show current progress
❯ history     Show completeness score history
❯ backends    List available LLM backends
❯ config      Generate config.yaml
❯ help        Show help
❯ quit        Exit
```

### How It Works
1. Place an `idea.md` file in any folder describing your project
2. Run the CLI from that folder
3. Type `go` - the agent will:
   - Create a `workspace/` directory
   - Initialize git repository
   - Copy your spec into the workspace
   - Start Agent 1 with prompt: "Build the complete project described in @idea.md"
   - Iterate until complete (or press Ctrl+C to pause)

## Configuration
Supports YAML config for:
- Model settings (name, backend, temperature)
- Limits (max iterations, runtime, commits)
- Agent prompts (separate prompts for implementation vs testing phases)
- Monitoring (log level, token tracking)
- Phase threshold (when to switch from implementation to testing)

## LLM Backends
- **Ollama**: Local LLM server (recommended for easy setup)
- **LM Studio**: GUI-based local LLM with model management
- **MLX**: Apple Silicon native (fastest on Mac)
- **OpenAI-compatible**: Any API endpoint (vLLM, text-gen-inference, etc.)

## Recent Changes
- Added dual Agent 2 prompts (implementation vs testing phases) - Dec 2025
- Added LM Studio backend support - Dec 2025
- Initial implementation - Dec 2025
