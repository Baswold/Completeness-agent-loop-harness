# CLI Backends for Completeness Loop

⚠️ **CRITICAL WARNING**: CLI backends use your Pro/Plus subscription credits and can consume them VERY QUICKLY during autonomous agent loops!

## Overview

The Completeness Loop now supports three CLI-based backends that use your existing AI subscriptions instead of API keys. This allows you to leverage your Pro/Plus subscriptions for CI/CD and automation.

**Important**: These backends are designed for users who want to use their subscription credits instead of API credits. Monitor your usage closely!

---

## Claude Code CLI Backend

Uses the official Claude Code CLI from Anthropic.

### Installation

1. **Install Claude Code CLI**
   ```bash
   # Visit https://claude.com/code for installation instructions
   # Or use the installer for your platform
   ```

2. **Authenticate**
   ```bash
   claude auth
   ```
   This will link your Anthropic Pro/Plus subscription.

3. **Verify Installation**
   ```bash
   claude -p "Hello, world!"
   ```

### Configuration

In your `config.yaml`:

```yaml
completeness_loop_config:
  model:
    backend: "claude-cli"
    name: "sonnet"              # Options: sonnet, opus, haiku
    max_tokens: 4096
    temperature: 0.7
```

### Available Models

- `sonnet` (claude-sonnet-4-5) - **Recommended** for complex tasks
- `opus` (claude-opus-4-5) - Most capable model
- `haiku` (claude-haiku-4-5) - Fast, lightweight (3x cost savings)

### Features

- Headless mode with `-p` flag
- Auto-approves tools with `--dangerously-skip-permissions`
- Model selection via `--model` flag
- Uses your Claude Pro/Plus subscription

### Monitoring Usage

Monitor your usage at: https://console.anthropic.com/

### Cost Implications

The Claude Code CLI uses your Anthropic Pro/Plus subscription credits. Autonomous agent loops can:
- Run for extended periods
- Make many sequential calls
- Execute multiple tool operations
- Consume credits rapidly

**Recommendation**: Start with small projects to understand usage patterns.

---

## OpenAI Codex CLI Backend

Uses the official OpenAI Codex CLI.

### Installation

1. **Install Codex CLI**
   ```bash
   # Via npm (recommended)
   npm i -g @openai/codex

   # Or via Homebrew
   brew install codex
   ```

2. **Authenticate**
   ```bash
   codex
   ```
   On first run, you'll be prompted to sign in with your ChatGPT account.

3. **Verify Installation**
   ```bash
   codex -m gpt-5-codex
   ```

### Configuration

In your `config.yaml`:

```yaml
completeness_loop_config:
  model:
    backend: "codex"
    name: "gpt-5-codex"         # Options: gpt-5-codex, gpt-5, gpt-4o
    max_tokens: 4096
    temperature: 0.7
```

### Available Models

- `gpt-5-codex` - **Recommended** - Optimized for agentic software engineering
- `gpt-5` - Latest flagship model
- `gpt-4o` - Previous generation (still available)

### Features

- Interactive terminal UI
- ChatGPT Pro, Plus, Business, or Enterprise subscription
- Model selection via `-m` flag or `/model` command
- Tool approval configuration via `/approvals`

### Monitoring Usage

Monitor your usage in your ChatGPT account settings.

### Cost Implications

The Codex CLI uses your ChatGPT Pro/Plus subscription. Be aware of:
- Message limits per hour/day
- Potential rate limiting
- Shared credits with ChatGPT web usage

---

## Google Gemini CLI Backend

Uses the official Google Gemini CLI.

### Installation

1. **Install Gemini CLI**
   ```bash
   # Follow instructions at:
   # https://github.com/google-gemini/gemini-cli

   # Typically via package manager or download
   ```

2. **Authenticate**
   ```bash
   gemini auth
   ```
   This will authenticate with your Google account.

3. **Verify Installation**
   ```bash
   gemini -p "Hello, world!"
   ```

### Configuration

In your `config.yaml`:

```yaml
completeness_loop_config:
  model:
    backend: "gemini"
    name: "gemini-2.5-flash"    # Options: gemini-2.5-flash, gemini-2.5-pro
    max_tokens: 4096
    temperature: 0.7
```

### Available Models

- `gemini-2.5-flash` - **Recommended** - Fast and efficient
- `gemini-2.5-pro` - More capable for complex tasks
- `gemini-3-pro` - Latest model (requires preview features enabled)

### Features

- Headless mode with `-p` flag
- Auto-approves with `--yolo` flag
- Model selection via `--model` flag
- JSON output with `--output-format json`

### Monitoring Usage

Monitor your usage at: https://aistudio.google.com/

### Cost Implications

The Gemini CLI uses your Google AI Studio / Vertex AI credits. Consider:
- Credit consumption rate
- Daily/monthly quotas
- Pricing differences between models

---

## Comparison: API vs CLI Backends

| Feature | API Backends | CLI Backends |
|---------|-------------|--------------|
| **Cost Model** | Pay per token | Subscription credits |
| **Best For** | Production, predictable costs | Development, testing |
| **Rate Limits** | API rate limits | Subscription limits |
| **Setup** | API key only | CLI installation + auth |
| **Tool Support** | Full structured tools | Natural language responses |
| **Monitoring** | API dashboard | Subscription dashboard |

---

## Best Practices

### 1. Start Small
Begin with small test projects to understand credit consumption patterns.

### 2. Monitor Usage
Check your subscription dashboard frequently when using CLI backends.

### 3. Set Iteration Limits
Configure lower `max_iterations` in your config when testing:

```yaml
limits:
  max_iterations: 10  # Reduced from default 50
  max_runtime_hours: 1  # Reduced from default 12
```

### 4. Use Appropriate Models
- For testing: Use faster, cheaper models (haiku, flash)
- For production: Use more capable models (sonnet, pro)

### 5. Consider Hybrid Approach
- Use API backends for production
- Use CLI backends for development/testing with your subscription

### 6. Watch for Warnings
The system will display warnings when CLI backends are active:

```
================================================================================
⚠️  WARNING: CLAUDE CODE CLI BACKEND ACTIVE
================================================================================
This backend uses your Anthropic Pro/Plus subscription!
Autonomous agent loops can consume credits VERY QUICKLY.
Monitor your usage at: https://console.anthropic.com/
================================================================================
```

**Do not ignore these warnings!**

---

## Troubleshooting

### CLI Not Found

**Error**: `'claude' command not found` (or `codex`, `gemini`)

**Solution**:
1. Verify the CLI is installed
2. Check it's in your PATH
3. Try running the command directly in terminal

### Authentication Failed

**Error**: Authentication or permission errors

**Solution**:
1. Run the auth command again: `claude auth`, `codex`, or `gemini auth`
2. Verify you have an active subscription
3. Check your account status on the provider's website

### Timeout Errors

**Error**: CLI command timed out

**Solution**:
1. The default timeout is 10 minutes
2. Check your internet connection
3. Try with a simpler prompt first
4. Consider using API backends for long-running operations

### Permission Errors

**Error**: Tool execution blocked or requires approval

**Solution**:
- The CLI backends automatically use permission bypass flags
- If you still see prompts, check the CLI installation
- For Claude Code: Verify `--dangerously-skip-permissions` is supported
- For Gemini: Verify `--yolo` flag is supported

---

## Cost Estimation

While exact costs vary, here's a rough estimate:

### Claude Code CLI (Anthropic Pro)
- Typical autonomous loop: 50-200 messages
- Pro plan: Limited messages per day
- **Estimate**: Can exhaust daily limit in 1-3 long sessions

### Codex CLI (ChatGPT Plus)
- Typical autonomous loop: 50-200 messages
- Plus plan: Limited messages per 3-4 hours
- **Estimate**: May hit rate limits during intensive use

### Gemini CLI (AI Studio)
- Pricing varies by model and usage
- Flash models: Lower cost
- Pro models: Higher cost
- **Estimate**: Monitor credit consumption closely

---

## When to Use CLI Backends

✅ **Good Use Cases**:
- Development and testing
- Small projects
- Experimenting with the system
- CI/CD with existing subscriptions
- Personal projects

❌ **Avoid For**:
- Large-scale production deployments
- Cost-sensitive applications
- High-volume automation
- Shared subscription accounts

---

## Support and Resources

### Claude Code CLI
- Documentation: https://code.claude.com/docs
- Installation: https://claude.com/code
- Support: https://support.anthropic.com/

### OpenAI Codex CLI
- Documentation: https://developers.openai.com/codex
- GitHub: https://github.com/openai/codex
- Installation: `npm i -g @openai/codex` or `brew install codex`

### Google Gemini CLI
- Documentation: https://geminicli.com/docs
- GitHub: https://github.com/google-gemini/gemini-cli
- Installation: https://github.com/google-gemini/gemini-cli

---

## Summary

CLI backends provide a convenient way to use your existing AI subscriptions with the Completeness Loop. However, they come with important caveats:

1. ⚠️ They consume subscription credits rapidly
2. ⚠️ They may have rate limits
3. ⚠️ They're best for development/testing
4. ⚠️ Monitor your usage closely

For production use, we recommend API backends with predictable, pay-per-token pricing.

**Use CLI backends responsibly and monitor your usage!**
