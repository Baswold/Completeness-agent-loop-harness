# Mistral Setup Guide

This completeness loop is now configured to run on **Mistral AI's Devstral Small 2** via the official API. This provides a fast, affordable, and high-quality coding agent.

## Quick Start (5 minutes)

### 1. Get Your Mistral API Key

1. Go to [https://console.mistral.ai/](https://console.mistral.ai/)
2. Sign up or log in
3. Create an API key in your account settings
4. Copy the key

### 2. Set Environment Variable

```bash
export MISTRAL_API_KEY="your-api-key-here"
```

To make it persistent, add to your shell profile (~/.zshrc, ~/.bashrc, etc.):
```bash
export MISTRAL_API_KEY="your-api-key-here"
```

### 3. Create Your Project

```bash
mkdir my-project
cd my-project

# Create a specification file
cat > idea.md << 'EOF'
# My Todo App
Build a command-line todo list manager with:
- Add, remove, complete tasks
- Save to JSON file
- List all tasks with status
- Mark tasks as done/pending
EOF
```

### 4. Run the Agent Loop

```bash
# From the completeness-loop directory
python /path/to/completeness-loop/main.py my-project

# Or from within your project directory
python /path/to/completeness-loop/main.py
```

Then type: `go`

## What You're Using

- **Model**: Devstral Small 2 (devstral-small-2505)
- **Size**: 24B parameters
- **Performance**: State-of-the-art for coding tasks
- **Cost**: $0.10/$0.30 per million tokens (input/output)
- **Speed**: Fast inference, suitable for autonomous loops

### Alternative Models

If you want to use a different Mistral model, edit your config:

```yaml
# In config.yaml or via CLI
completeness_loop_config:
  model:
    backend: mistral
    name: mistral-large-latest  # Or: mistral-small-latest
```

Then restart the agent loop.

## System Architecture

The completeness loop runs two agents on Mistral:

1. **Agent 1 (Implementation)**: Writes code based on your spec
2. **Agent 2 (Review)**: Reviews the code and provides feedback

Both agents run on the same Mistral backend, allowing them to iterate autonomously.

### Key Features

- ✓ Automatic git commits after each cycle
- ✓ Phase transitions (implementation → testing at 70% completeness)
- ✓ Token tracking and usage monitoring
- ✓ Resumable sessions with state persistence
- ✓ Air-gap principle: Agent 2 reviews only code, not Agent 1's explanations

## Configuration

### Default Config

The system defaults to:
```yaml
completeness_loop_config:
  model:
    backend: mistral
    name: devstral-small-2505
    max_tokens: 4096
    temperature: 0.7
  limits:
    max_iterations: 50
    max_runtime_hours: 12
    max_commits: 200
  agents:
    testing_phase_threshold: 70  # Switch to testing at 70% completeness
```

### Generate Custom Config

```bash
python /path/to/completeness-loop/main.py
> config
```

This creates `config.yaml` that you can edit.

## Monitoring Progress

While the loop runs:
```bash
python /path/to/completeness-loop/main.py my-project
> status
```

This shows:
- Current completeness score
- Cycle count
- Phase (implementation or testing)
- Token usage
- Elapsed time

## Troubleshooting

### Error: "MISTRAL_API_KEY environment variable not set"
**Solution**: Make sure you've set the environment variable:
```bash
export MISTRAL_API_KEY="your-key"
```

### Error: "Invalid Mistral API key" or 401 error
**Solution**: Check that your API key is correct:
1. Go to [https://console.mistral.ai/](https://console.mistral.ai/)
2. Verify your API key in account settings
3. Make sure there are no extra spaces in the key

### Error: "Rate limited" or 429 error
**Solution**: You've hit Mistral's rate limits. The system will automatically retry after a delay.

### Agent seems stuck or slow
**Solution**: Check:
1. Your internet connection
2. Mistral API status at [https://status.mistral.ai/](https://status.mistral.ai/)
3. Token usage in your account settings

## Pricing

Devstral Small 2 costs:
- **Input**: $0.10 per million tokens
- **Output**: $0.30 per million tokens

Example costs:
- Small project (~50K tokens): ~$0.03
- Medium project (~500K tokens): ~$0.30
- Large project (~2M tokens): ~$1.20

## Advanced Usage

### Custom Agent Prompts

You can customize how agents behave by setting custom prompts in `config.yaml`:

```yaml
completeness_loop_config:
  agents:
    agent1_system_prompt: path/to/custom_agent1_prompt.txt
    agent2_implementation_prompt: path/to/custom_implementation_prompt.txt
    agent2_testing_prompt: path/to/custom_testing_prompt.txt
```

### Integration with Other Services

The completeness loop uses standard tools:
- Git for version control
- File operations (read, write, delete)
- Bash execution (runs tests, installs packages, etc.)
- Python script execution

All of these work seamlessly with Mistral.

## Getting Help

If you encounter issues:

1. Check the logs in `workspace/.completeness_state.json`
2. Review the git history: `cd workspace && git log`
3. Run the test suite: `python test_mistral_integration.py`
4. Check Mistral's documentation: [https://docs.mistral.ai/](https://docs.mistral.ai/)

## For More Information

- **Mistral AI**: https://mistral.ai/
- **API Docs**: https://docs.mistral.ai/
- **Console**: https://console.mistral.ai/
- **Models**: https://docs.mistral.ai/capabilities/function_calling/

## Switching Back to Other Backends

To use a different LLM backend, just change the config:

```bash
python /path/to/completeness-loop/main.py
> settings
> 3  (Change backend)
> openai  (or: ollama, lmstudio, mlx)
```

Then the system will use that backend instead.
