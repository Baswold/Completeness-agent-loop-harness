# Completeness Loop - Autonomous Multi-Agent Coding System

A sophisticated autonomous multi-agent system that reads your project specification and builds complete, tested applications using an LLM backend of your choice. Built with modularity, extensibility, and production use in mind.

## What It Does

```
Your Idea (idea.md)
    ↓
[Agent 1: Implementation] → Creates code, runs tests, makes commits
    ↓
[Agent 2: Review] → Evaluates completeness (0-100%), gives feedback
    ↓
Repeat until complete (or you stop it)
    ↓
Production-ready project in workspace/ with git history
```

### Real Example Results

Starting spec: "Build a task manager CLI with add/list/complete/delete features"

- **Cycle 1** (2 mins): Initial implementation created, 0% complete
- **Cycle 2** (5 mins): Dramatically improved to 85% complete with proper tests
- **Result**: Fully functional Python app with ~150 lines of clean code

## Features

✅ **Two-Agent System**
- Agent 1: Writes code, runs tests, makes commits
- Agent 2: Reviews against spec, rates completeness, provides next steps

✅ **LLM Flexibility**
- Mistral (devstral-small-2505) - recommended, affordable
- OpenAI, Ollama, LM Studio, MLX, or any OpenAI-compatible API

✅ **Smart Iteration**
- Automatic phase transitions (implementation → testing at 70% complete)
- Token tracking and monitoring
- Git commits with completeness scores
- State persistence (pause/resume)

✅ **Production Ready**
- Comprehensive error handling
- Test integration
- Configurable limits and thresholds
- Extensive logging

✅ **Developer Friendly**
- Clean, modular architecture
- Extensive customization options
- Feature flags for optional behaviors
- Example projects included

## Quick Start (5 minutes)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Your LLM

**Option A: Mistral (Recommended)**
```bash
# Get API key from https://console.mistral.ai/
export MISTRAL_API_KEY="your-key-here"
```

**Option B: Other Backends**
- OpenAI: Set `OPENAI_API_KEY`
- Ollama: Run `ollama serve`
- LM Studio: Open the app and start local server

### 3. Create Your Project

```bash
mkdir my-project
cd my-project

cat > idea.md << 'EOF'
# My Todo App

Build a command-line todo manager with:
- Add, remove, complete tasks
- Save to JSON file
- List all tasks with status
EOF
```

### 4. Run the Agent Loop

```bash
python /path/to/main.py
```

Then:
```
Type 'go' and press Enter
```

**That's it!** Watch as the agents autonomously build your project.

## Architecture

```
completeness-loop/
├── src/
│   ├── llm.py          # LLM backend implementations
│   ├── agents.py       # Agent 1 & Agent 2 logic
│   ├── orchestrator.py # Main loop controller
│   ├── config.py       # Configuration models
│   ├── tools.py        # Tool registry (bash, file ops, git)
│   ├── context.py      # Context building for prompts
│   ├── prompts.py      # User-friendly prompt utilities
│   └── cli.py          # Interactive CLI interface
├── tests/              # Test suite
├── examples/           # Example projects
├── docs/               # Documentation
└── main.py             # Entry point
```

## Configuration

Default configuration uses Mistral's devstral-small-2505. Customize with `config.yaml`:

```yaml
completeness_loop_config:
  model:
    backend: mistral              # or: openai, ollama, lmstudio, mlx
    name: devstral-small-2505     # or: gpt-4o-mini, etc.
    max_tokens: 4096
    temperature: 0.7

  limits:
    max_iterations: 50
    max_runtime_hours: 12
    completion_threshold: 95      # Stop when >= 95% complete

  agents:
    testing_phase_threshold: 70   # Switch to testing at 70%

  features:
    refinement_mode: false        # Optional code polishing
    interactive_approval: false   # Approve changes before commit
    verbose_logging: false        # Detailed execution logs
    auto_fix_tests: true          # Automatic test repair
```

### Available Backends

| Backend | Setup | Cost | Best For |
|---------|-------|------|----------|
| **Mistral** | Get API key | $0.10-0.30/1M tokens | Fast, affordable coding |
| **OpenAI** | `OPENAI_API_KEY` | $0.15-0.60/1M tokens | Reliable, versatile |
| **Ollama** | `ollama serve` | Free | Local, privacy |
| **LM Studio** | Start app | Free | Guided local setup |
| **MLX** | `pip install mlx-lm` | Free | Apple Silicon native |

## Example Projects

Pre-configured examples in `examples/`:

```bash
cd examples/task-manager
python ../../main.py
# Type: go
```

Available examples:
- `task-manager/` - CLI task management app
- `simple-calculator/` - Math expression evaluator

## Commands

While the agents are running:

```
status    Show current score, cycle count, tokens used
history   Display completeness score history
pause     Pause the loop (resume later with 'resume')
backends  Show available LLM backends
settings  Change configuration
help      Show help
quit      Exit
```

## Advanced Usage

### Custom Agent Prompts

```yaml
agents:
  agent1_system_prompt: path/to/custom_prompt.txt
  agent2_implementation_prompt: path/to/review_prompt.txt
```

### Refinement Mode (Optional)

Enable to have agents polish and refine code after implementation:

```yaml
features:
  refinement_mode: true
```

### Interactive Approval

Ask user to confirm changes before commits:

```yaml
features:
  interactive_approval: true
```

### Verbose Logging

```yaml
monitoring:
  verbose_logging: true
  log_file: my_custom.log
```

## Key Design Decisions

### Air Gap Principle
Agent 2 reviews ONLY the code, not Agent 1's explanations. This prevents "same-model bias" where Agent 2 might accept incomplete work due to Agent 1's confident-sounding summaries.

### Phase Transitions
- **Implementation Phase** (0-70%): Focus on core features
- **Testing Phase** (70%+): Focus on comprehensive testing and edge cases

### Token Tracking
Full visibility into:
- Tokens per agent
- Total tokens used
- Estimated cost (with pricing displayed)

## Troubleshooting

### "Cannot connect to Mistral API"
- Check internet connection
- Verify API key is correct
- Check Mistral status: https://status.mistral.ai/

### "Agent seems stuck"
- Type `status` to check progress
- Common cause: tests failing repeatedly
- Solution: Let it continue (agents will debug)

### "0% completeness"
- Check that `idea.md` is readable and clear
- Complex specifications take longer
- Look at Agent 2's feedback for next steps

### Tests keep failing
- Ensure `auto_fix_tests: true` in config (default)
- Check test quality in `test_*.py` files
- Agent 1 will debug and improve

## Development

### Run Tests

```bash
# Unit tests
python -m pytest tests/test_mistral_integration.py -v

# End-to-end tests
python -m pytest tests/test_mistral_e2e.py -v

# Full demo
python tests/run_full_test.py
```

### Project Structure

```
src/
├── llm.py           # LLMBackend base class + implementations
├── agents.py        # Agent1, Agent2, AgentResponse classes
├── orchestrator.py  # Orchestrator - main loop
├── config.py        # Configuration models
├── tools.py         # Tool implementations (bash, file, git)
├── context.py       # Context building for agents
├── prompts.py       # User-friendly prompts
└── cli.py           # REPL interface
```

## Extending the System

### Add a New Backend

1. Subclass `LLMBackend` in `src/llm.py`
2. Implement `generate()` method
3. Add to `create_backend()` factory
4. Update documentation

### Add Custom Tools

1. Implement tool function in `src/tools.py`
2. Register with `ToolRegistry.register()`
3. Include tool schema for agent visibility

### Customize Agent Behavior

1. Write custom system prompt
2. Configure in `config.yaml`
3. Pass to Agent1/Agent2 during init

## Documentation

- **[SETUP.md](docs/SETUP.md)** - Detailed setup and configuration guide
- **[MISTRAL_SETUP.md](docs/MISTRAL_SETUP.md)** - Mistral-specific setup
- **[Architecture](docs/)** - Technical architecture details
- **[Examples](examples/)** - Real project specs to learn from

## Performance

Typical performance with Mistral's devstral-small-2505:

| Task | Cycles | Time | Cost |
|------|--------|------|------|
| Simple Calculator | 2 | 5 min | $0.05 |
| Task Manager | 2 | 8 min | $0.16 |
| API Server | 3+ | 15+ min | $0.40+ |

## Cost Estimates

Using Mistral devstral-small-2505 ($0.10/$0.30 per 1M tokens):

```
Small project (50K tokens)  ≈ $0.03
Medium project (500K tokens) ≈ $0.30
Large project (2M tokens)   ≈ $1.20
```

## License

This project is provided as-is for educational and commercial use.

## Contributing

This is a personal project, but you're welcome to fork and extend it!

Some ideas:
- Additional LLM backends
- More sophisticated testing strategies
- Better cost optimization
- UI improvements
- Integration with CI/CD

---

**Ready to build? Start with `python main.py` and type `go`!** 🚀
