# Setup and Configuration Guide

Complete guide to setting up the Completeness Loop for your system.

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Git (for version control)
- An LLM API key or local LLM running

## Installation

### 1. Clone or Download

```bash
git clone https://github.com/yourusername/completeness-loop.git
cd completeness-loop
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**What's installed:**
- `click` - CLI framework
- `rich` - Pretty terminal output
- `pydantic` - Configuration validation
- `pyyaml` - YAML config files
- `httpx` - HTTP client
- `openai` - OpenAI SDK (optional)
- `gitpython` - Git operations
- `watchdog` - File monitoring
- `prompt_toolkit` - User input

## LLM Backend Setup

Choose your LLM backend based on your needs:

### Option 1: Mistral API (Recommended) ⭐

**Why Mistral?**
- Fast and affordable ($0.10-0.30 per 1M tokens)
- Devstral Small 2 is #1 for coding tasks
- OpenAI-compatible API
- Easy setup - just need API key

**Setup:**

1. Go to https://console.mistral.ai/
2. Create an account
3. Generate an API key
4. Set environment variable:

```bash
export MISTRAL_API_KEY="your-key-here"
```

**To make it permanent, add to your shell profile:**

```bash
# For .zshrc (macOS default):
echo 'export MISTRAL_API_KEY="your-key-here"' >> ~/.zshrc
source ~/.zshrc

# For .bashrc (Linux):
echo 'export MISTRAL_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

**Verify setup:**
```bash
python -c "from src.llm import MistralBackend; print('✓ Mistral configured')"
```

---

### Option 2: OpenAI API

**Setup:**

1. Get API key from https://platform.openai.com/
2. Set environment variable:

```bash
export OPENAI_API_KEY="sk-..."
```

**Or use Replit AI Integrations (auto-configured):**

```bash
# In Replit, just set backend in config.yaml:
model:
  backend: openai
  name: gpt-4o-mini
```

---

### Option 3: Ollama (Local)

**Benefits:**
- No API key needed
- Runs completely locally
- Free
- Good privacy

**Setup:**

1. Install Ollama:
   ```bash
   brew install ollama  # macOS
   # Or download from https://ollama.ai
   ```

2. Pull a model:
   ```bash
   ollama pull devstral
   # Or: mistral, codestral, llama2, etc.
   ```

3. Start the server:
   ```bash
   ollama serve
   # Runs on http://localhost:11434
   ```

4. Configure (in `config.yaml`):
   ```yaml
   model:
     backend: ollama
     name: devstral
     base_url: http://localhost:11434
   ```

---

### Option 4: LM Studio (Local with GUI)

**Benefits:**
- Easy model management with GUI
- Supports many models
- Free
- Local only

**Setup:**

1. Download from https://lmstudio.ai
2. Open LM Studio app
3. Load a model (e.g., Devstral, CodeLlama)
4. Start local server (button in app)
5. Configure (in `config.yaml`):
   ```yaml
   model:
     backend: lmstudio
     name: local-model
     base_url: http://localhost:1234
   ```

---

### Option 5: MLX (Apple Silicon)

**Benefits:**
- Fastest option for Mac M1/M2/M3
- Native performance
- Free

**Setup:**

1. Install mlx-lm:
   ```bash
   pip install mlx-lm
   ```

2. Configure (in `config.yaml`):
   ```yaml
   model:
     backend: mlx
     name: mistralai/Devstral-Small-2-24B-Instruct
   ```

3. First run will download the model (takes a minute)

---

## Configuration

### Quick Setup (Defaults)

The system works out-of-the-box with defaults using Mistral API. Just:

```bash
export MISTRAL_API_KEY="your-key"
python main.py
```

### Customization (config.yaml)

Create `config.yaml` in your project directory:

```yaml
completeness_loop_config:

  # Model settings
  model:
    backend: mistral              # mistral, openai, ollama, lmstudio, mlx
    name: devstral-small-2505     # Model identifier
    max_tokens: 4096              # Max tokens per request
    temperature: 0.7              # 0=deterministic, 1=creative
    base_url: null                # Optional: override API endpoint

  # Execution limits
  limits:
    max_iterations: 50            # Max cycles before stopping
    max_runtime_hours: 12         # Time limit
    max_commits: 200              # Stop after this many commits
    completion_threshold: 95      # Auto-stop at this % complete

  # Agent configuration
  agents:
    agent1_system_prompt: null    # Optional: custom prompt file
    agent2_implementation_prompt: null
    agent2_testing_prompt: null
    agent1_context_token_limit: 32000
    agent2_context_token_limit: 32000
    testing_phase_threshold: 70   # Switch to testing at 70% complete

  # Monitoring
  monitoring:
    log_level: INFO               # DEBUG, INFO, WARNING, ERROR
    token_tracking: true          # Track and display token usage
    log_file: completeness_loop.log

  # Optional features
  features:
    refinement_mode: false        # Let agents refine code after implementation
    interactive_approval: false   # Ask user to approve changes
    verbose_logging: false        # Very detailed logs
    auto_fix_tests: true          # Automatically fix failing tests
```

### Generate Default Config

```bash
python main.py
# Press: config
# Creates: config.yaml
```

---

## Project Setup

### Structure

Create a directory for your project:

```
my-project/
├── idea.md              # Your specification
├── config.yaml          # (Optional) custom configuration
└── workspace/           # (Created automatically)
    ├── .git/            # Git repository
    ├── main.py          # Generated code
    ├── tests/           # Generated tests
    └── ...
```

### Writing Your Specification

Create `idea.md` with clear description:

```markdown
# My Project Name

Short description of what you want to build.

## Features
- Feature 1
- Feature 2
- Feature 3

## Technical Requirements
- Language/framework preferences
- Specific libraries to use
- File structure preferences
- Any constraints

## Example
[Show example usage if applicable]
```

**Tips:**
- Be specific about requirements
- Include examples
- Mention constraints
- Keep it concise but complete

### Example Specifications

See `examples/` folder:

```bash
examples/
├── task-manager/
│   └── idea.md          # CLI task manager spec
└── simple-calculator/
    └── idea.md          # Math expression calculator spec
```

---

## Running the System

### Basic Usage

```bash
# 1. Create project directory
mkdir my-project
cd my-project

# 2. Create specification
cat > idea.md << 'EOF'
# My App
Build a simple app that...
EOF

# 3. Run the CLI
python /path/to/main.py

# 4. Start the loop
Type: go
```

### Interactive Commands

While running:

```
go              Start/configure new session
resume          Continue paused session
status          Show current progress
history         Display score over time
settings        Change configuration
backends        Show available backends
config          Generate config.yaml
help            Show help
quit            Exit
```

### Monitoring Progress

The agents show:
- Current completeness score (%)
- Cycle number
- Tokens used per cycle
- Completed items
- Remaining work

---

## Troubleshooting

### API Connection Issues

**Error: "Cannot connect to Mistral API"**
- Check internet connection
- Verify API key: `echo $MISTRAL_API_KEY`
- Check Mistral status: https://status.mistral.ai/

**Error: "Invalid API key" (401)**
- Verify key in console.mistral.ai
- No extra spaces: `export MISTRAL_API_KEY="key-here"`
- Not in quotes: `key-here`, not `"key-here"`

**Error: "Rate limited" (429)**
- Wait a moment and retry
- Mistral limit: ~2500 requests/minute
- Usually resolves automatically

### Missing Dependencies

**ModuleNotFoundError**

```bash
pip install -r requirements.txt --upgrade
```

### Agent Performance Issues

**Agents making no progress**
- Check `idea.md` is clear and specific
- Too complex? Break it into smaller steps
- Look at feedback - agents explain what's missing

**Tests keep failing**
- Enable `auto_fix_tests: true` in config
- Agents will automatically debug
- Check test output in logs

**Slow iterations**
- Complex specs take longer
- Increase `max_tokens` to 8192 for more capability
- Consider breaking into smaller projects

### Configuration Issues

**Using wrong backend**
- Check `config.yaml` exists in project directory
- Verify `backend:` setting
- Run `python main.py` then `backends` to list available

---

## Environment Setup by OS

### macOS

```bash
# Install Python 3.8+ (if needed)
brew install python@3.11

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up Mistral
export MISTRAL_API_KEY="your-key-here"
echo 'export MISTRAL_API_KEY="your-key-here"' >> ~/.zshrc

# Run
python main.py
```

### Linux

```bash
# Install Python 3.8+
sudo apt-get install python3.11 python3.11-venv

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up Mistral
export MISTRAL_API_KEY="your-key-here"
echo 'export MISTRAL_API_KEY="your-key-here"' >> ~/.bashrc

# Run
python main.py
```

### Windows

```powershell
# Install Python 3.8+ from python.org

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up Mistral (PowerShell)
$env:MISTRAL_API_KEY = "your-key-here"
[Environment]::SetEnvironmentVariable("MISTRAL_API_KEY", "your-key-here", "User")

# Run
python main.py
```

---

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Set up LLM backend (Mistral recommended)
3. ✅ Create project with `idea.md`
4. ✅ Run `python main.py`
5. ✅ Type `go` and watch it build!

---

## Getting Help

- **Documentation**: See `docs/` folder
- **Examples**: See `examples/` folder
- **Tests**: `python -m pytest tests/ -v`
- **Configuration**: Run `python main.py` then `help`

Enjoy building with autonomous agents! 🚀
