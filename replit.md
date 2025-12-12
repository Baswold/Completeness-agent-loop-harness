# Completeness Agent Loop

## Overview
An autonomous multi-agent CLI system that completes complex coding tasks overnight using a review-loop pattern with automatic git backups. Uses local LLM inference (Devstral Small 2 via MLX/Ollama) to run independently without human intervention.

## Architecture

### Two-Agent System
- **Agent 1 (Implementation)**: Receives instructions, implements code, runs tests, makes commits
- **Agent 2 (Review/Persistence)**: Reviews codebase against spec, rates completeness (0-100%), generates next instructions

### Key Design Decision
Agent 2 NEVER sees Agent 1's self-assessments or explanations - only the code. This prevents same-model bias where Agent 2 might be persuaded by Agent 1's confident-but-wrong summaries.

## Project Structure
```
src/
├── __init__.py       # Package init
├── config.py         # Configuration with Pydantic models
├── llm.py            # LLM backends (Ollama, MLX, HTTP)
├── tools.py          # Tool registry for Agent 1 (bash, files, git)
├── agents.py         # Agent 1 and Agent 2 implementations
├── context.py        # Context building for agent prompts
├── orchestrator.py   # Main loop controller
└── cli.py            # Rich CLI interface with dashboard
main.py               # Entry point
```

## Usage

```bash
# Start a new task
python main.py start --idea ./my-project-idea.md --workspace ./sandbox

# Resume interrupted task
python main.py start --idea ./idea.md --workspace ./sandbox --resume

# Check status
python main.py status --workspace ./sandbox

# View score history
python main.py score --workspace ./sandbox

# Generate config file
python main.py init-config --output config.yaml
```

## Configuration
Supports YAML config for:
- Model settings (name, backend, temperature)
- Limits (max iterations, runtime, commits)
- Agent prompts (custom system prompts)
- Monitoring (log level, token tracking)

## LLM Backends
- **Ollama**: Local LLM server (recommended for easy setup)
- **MLX**: Apple Silicon native (for Mac users)
- **HTTP**: Any OpenAI-compatible API

## Recent Changes
- Initial implementation (Dec 2025)
