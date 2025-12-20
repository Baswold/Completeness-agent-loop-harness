import json
import httpx
import subprocess
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )


@dataclass
class LLMResponse:
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = "stop"


class LLMBackend(ABC):
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        pass
    
    @abstractmethod
    def supports_tools(self) -> bool:
        pass
    
    @abstractmethod
    def get_info(self) -> str:
        pass


class OllamaBackend(LLMBackend):
    """
    Ollama backend - local LLM server
    Default URL: http://localhost:11434
    
    Setup:
        brew install ollama
        ollama pull devstral  # or codestral, llama3, etc.
        ollama serve
    """
    def __init__(self, model: str = "devstral", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=300.0)
    
    def get_info(self) -> str:
        return f"Ollama ({self.model}) @ {self.base_url}"
    
    def supports_tools(self) -> bool:
        return True
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            }
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            message = data.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                ),
                finish_reason="tool_calls" if tool_calls else "stop"
            )
        except httpx.ConnectError:
            return LLMResponse(
                content="Error: Cannot connect to Ollama. Make sure Ollama is running (ollama serve)",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling Ollama: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class LMStudioBackend(LLMBackend):
    """
    LM Studio backend - local LLM with OpenAI-compatible API
    Default URL: http://localhost:1234
    
    Setup:
        1. Download LM Studio from https://lmstudio.ai
        2. Load a model (e.g., Devstral, CodeLlama, DeepSeek Coder)
        3. Start the local server (default port 1234)
    """
    def __init__(self, model: str = "local-model", base_url: str = "http://localhost:1234"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=300.0)
    
    def get_info(self) -> str:
        return f"LM Studio ({self.model}) @ {self.base_url}"
    
    def supports_tools(self) -> bool:
        return True
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage_data = data.get("usage", {})
            
            return LLMResponse(
                content=message.get("content", "") or "",
                tool_calls=message.get("tool_calls", []) or [],
                usage=TokenUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                ),
                finish_reason=choice.get("finish_reason", "stop")
            )
        except httpx.ConnectError:
            return LLMResponse(
                content="Error: Cannot connect to LM Studio. Make sure the local server is running on port 1234.",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling LM Studio: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class MLXBackend(LLMBackend):
    """
    MLX backend - native Apple Silicon inference
    Requires: pip install mlx-lm
    
    Best for Mac users with M1/M2/M3/M4 chips.
    """
    def __init__(self, model: str = "mistralai/Devstral-Small-2-24B-Instruct"):
        self.model_name = model
        self._model = None
        self._tokenizer = None
    
    def get_info(self) -> str:
        return f"MLX ({self.model_name})"
    
    def _load_model(self):
        if self._model is None:
            try:
                from mlx_lm import load
                self._model, self._tokenizer = load(self.model_name)
            except ImportError:
                raise ImportError("mlx-lm not installed. Install with: pip install mlx-lm")
    
    def supports_tools(self) -> bool:
        return False
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self._load_model()
        
        try:
            from mlx_lm import generate
            
            prompt = self._format_messages(messages)
            prompt_tokens = len(self._tokenizer.encode(prompt))
            
            response = generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                temp=temperature
            )
            
            completion_tokens = len(self._tokenizer.encode(response))
            
            return LLMResponse(
                content=response,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error with MLX: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                formatted.append(f"[INST] {content} [/INST]")
            elif role == "user":
                formatted.append(f"[INST] {content} [/INST]")
            elif role == "assistant":
                formatted.append(content)
        return "\n".join(formatted)


class OpenAIBackend(LLMBackend):
    """
    OpenAI API backend using the official OpenAI Python client.
    Automatically uses Replit AI Integrations credentials if available.
    """
    def __init__(self, model: str = "gpt-4o"):
        import os
        from openai import OpenAI
        
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
        
        if base_url and api_key:
            self.model = model
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            return
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            self.model = model
            self.client = OpenAI(api_key=api_key)
            return
        
        raise ValueError(
            "No OpenAI API key found.\n"
            "Set OPENAI_API_KEY environment variable or use Replit AI Integrations."
        )
    
    def get_info(self) -> str:
        return f"OpenAI ({self.model})"
    
    def supports_tools(self) -> bool:
        return True
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            if tools:
                kwargs["tools"] = tools
            
            response = self.client.chat.completions.create(**kwargs)
            
            choice = response.choices[0]
            message = choice.message
            usage = response.usage
            
            tool_calls_list = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls_list.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })
            
            return LLMResponse(
                content=message.content or "",
                tool_calls=tool_calls_list,
                usage=TokenUsage(
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0
                ),
                finish_reason=choice.finish_reason or "stop"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling OpenAI: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class MistralBackend(LLMBackend):
    """
    Mistral API backend - OpenAI-compatible API
    Default: https://api.mistral.ai/v1

    Setup:
        1. Get API key from https://console.mistral.ai/
        2. Set environment variable: export MISTRAL_API_KEY="your-key"
        3. Use model: devstral-small-2505 (recommended for coding)

    Available models:
        - devstral-small-2505: Fast, 24B parameter coding model (recommended)
        - mistral-small-latest: General purpose 24B model
        - mistral-large-latest: Powerful 123B equivalent model
    """
    def __init__(self, model: str = "devstral-small-2505"):
        import os

        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY environment variable not set.\n"
                "Get your API key from https://console.mistral.ai/\n"
                "Then run: export MISTRAL_API_KEY='your-key'"
            )

        self.model = model
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"
        self.client = httpx.Client(timeout=300.0)

    def get_info(self) -> str:
        return f"Mistral ({self.model}) @ {self.base_url}"

    def supports_tools(self) -> bool:
        return True

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            payload["tools"] = tools

        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage_data = data.get("usage", {})

            tool_calls = []
            if "tool_calls" in message:
                tool_calls = message.get("tool_calls", [])

            return LLMResponse(
                content=message.get("content", "") or "",
                tool_calls=tool_calls,
                usage=TokenUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                ),
                finish_reason=choice.get("finish_reason", "stop")
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return LLMResponse(
                    content="Error: Invalid Mistral API key. Check your MISTRAL_API_KEY environment variable.",
                    usage=TokenUsage(),
                    finish_reason="error"
                )
            elif e.response.status_code == 429:
                return LLMResponse(
                    content="Error: Rate limited by Mistral API. Please wait and retry.",
                    usage=TokenUsage(),
                    finish_reason="error"
                )
            else:
                return LLMResponse(
                    content=f"Error: Mistral API returned status {e.response.status_code}",
                    usage=TokenUsage(),
                    finish_reason="error"
                )
        except httpx.ConnectError:
            return LLMResponse(
                content="Error: Cannot connect to Mistral API. Check your internet connection.",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling Mistral API: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class OpenRouterBackend(LLMBackend):
    """
    OpenRouter API backend - OpenAI-compatible API with access to 100+ models
    Default: https://openrouter.ai/api/v1

    Setup:
        1. Get API key from https://openrouter.ai/
        2. Set environment variable: export OPENROUTER_API_KEY="your-key"
        3. Use any model from their catalog (e.g., anthropic/claude-3.5-sonnet)

    Popular models:
        - anthropic/claude-3.5-sonnet: Powerful reasoning and coding
        - anthropic/claude-3-opus: Most capable Claude model
        - google/gemini-2.0-flash-exp: Fast and capable
        - openai/gpt-4-turbo: Latest GPT-4 Turbo
        - meta-llama/llama-3.1-405b-instruct: Open source flagship
        - qwen/qwen-2.5-coder-32b-instruct: Specialized coding model

    See full model list: https://openrouter.ai/models
    """
    def __init__(self, model: str = "anthropic/claude-3.5-sonnet"):
        import os

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable not set.\n"
                "Get your API key from https://openrouter.ai/\n"
                "Then run: export OPENROUTER_API_KEY='your-key'"
            )

        self.model = model
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.client = httpx.Client(timeout=300.0)

    def get_info(self) -> str:
        return f"OpenRouter ({self.model}) @ {self.base_url}"

    def supports_tools(self) -> bool:
        return True

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/Baswold/Completeness-agent-loop-harness",  # Optional, for rankings
            "X-Title": "Completeness Agent Loop"  # Optional, for rankings
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            payload["tools"] = tools

        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage_data = data.get("usage", {})

            tool_calls = []
            if "tool_calls" in message:
                tool_calls = message.get("tool_calls", [])

            return LLMResponse(
                content=message.get("content", "") or "",
                tool_calls=tool_calls,
                usage=TokenUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                ),
                finish_reason=choice.get("finish_reason", "stop")
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return LLMResponse(
                    content="Error: Invalid OpenRouter API key. Check your OPENROUTER_API_KEY environment variable.",
                    usage=TokenUsage(),
                    finish_reason="error"
                )
            elif e.response.status_code == 429:
                return LLMResponse(
                    content="Error: Rate limited by OpenRouter API. Please wait and retry.",
                    usage=TokenUsage(),
                    finish_reason="error"
                )
            elif e.response.status_code == 402:
                return LLMResponse(
                    content="Error: Insufficient credits in OpenRouter account. Please add credits at https://openrouter.ai/",
                    usage=TokenUsage(),
                    finish_reason="error"
                )
            else:
                error_msg = f"Error: OpenRouter API returned status {e.response.status_code}"
                try:
                    error_data = e.response.json()
                    if "error" in error_data:
                        error_msg += f": {error_data['error'].get('message', '')}"
                except:
                    pass
                return LLMResponse(
                    content=error_msg,
                    usage=TokenUsage(),
                    finish_reason="error"
                )
        except httpx.ConnectError:
            return LLMResponse(
                content="Error: Cannot connect to OpenRouter API. Check your internet connection.",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling OpenRouter API: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class AnthropicBackend(LLMBackend):
    """
    Anthropic Claude API backend.
    Uses the official Anthropic Python SDK.

    Setup:
        1. Get API key from https://console.anthropic.com/
        2. Set environment variable: export ANTHROPIC_API_KEY="your-key"
        3. Use model: claude-3-5-sonnet-20241022 (recommended for coding)

    Available models:
        - claude-3-5-sonnet-20241022: Best for complex tasks (recommended)
        - claude-3-opus-20250219: Most capable for difficult tasks
        - claude-3-haiku-20240307: Fast, lightweight
    """
    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        import os
        from anthropic import Anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set.\n"
                "Get your API key from https://console.anthropic.com/\n"
                "Then run: export ANTHROPIC_API_KEY='your-key'"
            )

        self.model = model
        self.client = Anthropic(api_key=api_key)

    def get_info(self) -> str:
        return f"Anthropic ({self.model})"

    def supports_tools(self) -> bool:
        return True

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        try:
            # Convert tool definitions to Anthropic format if needed
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            # Extract content and tool calls
            content = ""
            tool_calls_list = []

            for block in response.content:
                if hasattr(block, "text"):
                    content = block.text
                elif block.type == "tool_use":
                    tool_calls_list.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input)
                        }
                    })

            return LLMResponse(
                content=content,
                tool_calls=tool_calls_list,
                usage=TokenUsage(
                    prompt_tokens=response.usage.input_tokens if response.usage else 0,
                    completion_tokens=response.usage.output_tokens if response.usage else 0,
                    total_tokens=(response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
                ),
                finish_reason=response.stop_reason or "stop"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling Anthropic: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class ClaudeCodeCLIBackend(LLMBackend):
    """
    Claude Code CLI backend - uses the 'claude' command-line interface.

    ⚠️  WARNING: This backend uses your Anthropic Pro subscription!
    CLI usage can consume credits VERY QUICKLY during autonomous agent loops.

    Setup:
        1. Install Claude Code CLI from https://claude.com/code
        2. Authenticate: claude auth
        3. Configure model: claude --model sonnet (or opus, haiku)

    Features:
        - Runs in headless mode with -p flag
        - Auto-approves tools with --dangerously-skip-permissions
        - Model selection via --model flag
        - Uses Claude Pro/Plus subscription credits

    Models:
        - sonnet (claude-sonnet-4-5): Recommended for complex tasks
        - opus (claude-opus-4-5): Most capable model
        - haiku (claude-haiku-4-5): Fast, lightweight (3x cost savings)
    """
    def __init__(self, model: str = "sonnet"):
        self.model = model
        self._warned = False

    def get_info(self) -> str:
        return f"Claude Code CLI ({self.model}) ⚠️ USES SUBSCRIPTION CREDITS"

    def supports_tools(self) -> bool:
        # CLI mode doesn't support structured tool calls in the same way
        # The agent will need to work with the CLI's natural responses
        return False

    def _show_warning(self):
        """Show usage warning once per session."""
        if not self._warned:
            print("\n" + "="*80)
            print("⚠️  WARNING: CLAUDE CODE CLI BACKEND ACTIVE")
            print("="*80)
            print("This backend uses your Anthropic Pro/Plus subscription!")
            print("Autonomous agent loops can consume credits VERY QUICKLY.")
            print("Monitor your usage at: https://console.anthropic.com/")
            print("="*80 + "\n")
            self._warned = True

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self._show_warning()

        try:
            # Combine messages into a single prompt
            # System messages become part of the context
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "system":
                    prompt_parts.append(f"SYSTEM CONTEXT:\n{content}\n")
                elif role == "user":
                    prompt_parts.append(f"USER:\n{content}\n")
                elif role == "assistant":
                    prompt_parts.append(f"ASSISTANT:\n{content}\n")

            full_prompt = "\n".join(prompt_parts)

            # Build command
            cmd = [
                "claude",
                "-p", full_prompt,
                "--model", self.model,
                "--dangerously-skip-permissions"
            ]

            # Run command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error running claude CLI"
                return LLMResponse(
                    content=f"Error running claude CLI: {error_msg}",
                    usage=TokenUsage(),
                    finish_reason="error"
                )

            # Extract output
            output = result.stdout.strip()

            # Estimate token usage (very rough approximation)
            # ~4 characters per token
            prompt_tokens = len(full_prompt) // 4
            completion_tokens = len(output) // 4

            return LLMResponse(
                content=output,
                tool_calls=[],
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                ),
                finish_reason="stop"
            )

        except subprocess.TimeoutExpired:
            return LLMResponse(
                content="Error: claude CLI command timed out after 10 minutes",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except FileNotFoundError:
            return LLMResponse(
                content="Error: 'claude' command not found. Install Claude Code CLI from https://claude.com/code",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling claude CLI: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class CodexCLIBackend(LLMBackend):
    """
    OpenAI Codex CLI backend - uses the 'codex' command-line interface.

    ⚠️  WARNING: This backend uses your ChatGPT Pro/Plus subscription!
    CLI usage can consume credits VERY QUICKLY during autonomous agent loops.

    Setup:
        1. Install: npm i -g @openai/codex  OR  brew install codex
        2. Authenticate: codex (first run will prompt for login)
        3. Configure approvals: Use /approvals command in interactive mode

    Features:
        - Uses ChatGPT Pro, Plus, Business, or Enterprise subscription
        - Supports GPT-5-Codex and GPT-5 models
        - Model selection via -m flag or /model command

    Models:
        - gpt-5-codex (default): Optimized for agentic software engineering
        - gpt-5: Latest flagship model
        - gpt-4o: Previous generation (still available)
    """
    def __init__(self, model: str = "gpt-5-codex"):
        self.model = model
        self._warned = False

    def get_info(self) -> str:
        return f"Codex CLI ({self.model}) ⚠️ USES SUBSCRIPTION CREDITS"

    def supports_tools(self) -> bool:
        return False

    def _show_warning(self):
        """Show usage warning once per session."""
        if not self._warned:
            print("\n" + "="*80)
            print("⚠️  WARNING: CODEX CLI BACKEND ACTIVE")
            print("="*80)
            print("This backend uses your ChatGPT Pro/Plus subscription!")
            print("Autonomous agent loops can consume credits VERY QUICKLY.")
            print("Monitor your usage in your ChatGPT account settings.")
            print("="*80 + "\n")
            self._warned = True

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self._show_warning()

        try:
            # Combine messages into a prompt
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "system":
                    prompt_parts.append(f"SYSTEM CONTEXT:\n{content}\n")
                elif role == "user":
                    prompt_parts.append(f"USER:\n{content}\n")
                elif role == "assistant":
                    prompt_parts.append(f"ASSISTANT:\n{content}\n")

            full_prompt = "\n".join(prompt_parts)

            # Create a temporary file with the prompt
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(full_prompt)
                prompt_file = f.name

            try:
                # Build command - pipe the prompt to codex
                # Using echo with heredoc to provide input
                cmd = f"cat {shlex.quote(prompt_file)} | codex -m {shlex.quote(self.model)}"

                # Run command via shell (needed for piping)
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=600
                )

                if result.returncode != 0:
                    error_msg = result.stderr or "Unknown error running codex CLI"
                    return LLMResponse(
                        content=f"Error running codex CLI: {error_msg}",
                        usage=TokenUsage(),
                        finish_reason="error"
                    )

                output = result.stdout.strip()

                # Estimate tokens
                prompt_tokens = len(full_prompt) // 4
                completion_tokens = len(output) // 4

                return LLMResponse(
                    content=output,
                    tool_calls=[],
                    usage=TokenUsage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens
                    ),
                    finish_reason="stop"
                )
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(prompt_file)
                except:
                    pass

        except subprocess.TimeoutExpired:
            return LLMResponse(
                content="Error: codex CLI command timed out after 10 minutes",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except FileNotFoundError:
            return LLMResponse(
                content="Error: 'codex' command not found. Install with: npm i -g @openai/codex OR brew install codex",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling codex CLI: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class GeminiCLIBackend(LLMBackend):
    """
    Google Gemini CLI backend - uses the 'gemini' command-line interface.

    ⚠️  WARNING: This backend uses your Google AI Studio / Vertex AI credits!
    CLI usage can consume credits VERY QUICKLY during autonomous agent loops.

    Setup:
        1. Install from https://github.com/google-gemini/gemini-cli
        2. Authenticate: gemini auth (will use Google account)
        3. Optional: Set default model with GEMINI_MODEL env var

    Features:
        - Runs in headless mode with -p flag
        - Auto-approves with --yolo flag (skips confirmations)
        - Model selection via --model flag
        - Supports Gemini 2.5 Flash, Pro, and Gemini 3 models

    Models:
        - gemini-2.5-flash: Fast, efficient (default)
        - gemini-2.5-pro: More capable for complex tasks
        - gemini-3-pro: Latest model (requires preview features)
    """
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
        self._warned = False

    def get_info(self) -> str:
        return f"Gemini CLI ({self.model}) ⚠️ USES API CREDITS"

    def supports_tools(self) -> bool:
        return False

    def _show_warning(self):
        """Show usage warning once per session."""
        if not self._warned:
            print("\n" + "="*80)
            print("⚠️  WARNING: GEMINI CLI BACKEND ACTIVE")
            print("="*80)
            print("This backend uses your Google AI Studio / Vertex AI credits!")
            print("Autonomous agent loops can consume credits VERY QUICKLY.")
            print("Monitor your usage at: https://aistudio.google.com/")
            print("="*80 + "\n")
            self._warned = True

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self._show_warning()

        try:
            # Combine messages
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "system":
                    prompt_parts.append(f"SYSTEM CONTEXT:\n{content}\n")
                elif role == "user":
                    prompt_parts.append(f"USER:\n{content}\n")
                elif role == "assistant":
                    prompt_parts.append(f"ASSISTANT:\n{content}\n")

            full_prompt = "\n".join(prompt_parts)

            # Build command
            cmd = [
                "gemini",
                "-p", full_prompt,
                "--model", self.model,
                "--yolo"  # Skip confirmations for automation
            ]

            # Run command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error running gemini CLI"
                return LLMResponse(
                    content=f"Error running gemini CLI: {error_msg}",
                    usage=TokenUsage(),
                    finish_reason="error"
                )

            output = result.stdout.strip()

            # Estimate tokens
            prompt_tokens = len(full_prompt) // 4
            completion_tokens = len(output) // 4

            return LLMResponse(
                content=output,
                tool_calls=[],
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                ),
                finish_reason="stop"
            )

        except subprocess.TimeoutExpired:
            return LLMResponse(
                content="Error: gemini CLI command timed out after 10 minutes",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except FileNotFoundError:
            return LLMResponse(
                content="Error: 'gemini' command not found. Install from https://github.com/google-gemini/gemini-cli",
                usage=TokenUsage(),
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling gemini CLI: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class OpenAICompatibleBackend(LLMBackend):
    """
    Generic OpenAI-compatible API backend.
    Works with any server that implements the OpenAI chat completions API.
    """
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.client = httpx.Client(timeout=300.0)
    
    def get_info(self) -> str:
        return f"OpenAI-compatible ({self.model}) @ {self.base_url}"
    
    def supports_tools(self) -> bool:
        return True
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage_data = data.get("usage", {})
            
            return LLMResponse(
                content=message.get("content", "") or "",
                tool_calls=message.get("tool_calls", []) or [],
                usage=TokenUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                ),
                finish_reason=choice.get("finish_reason", "stop")
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling API: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


# Backend aliases for convenience
BACKEND_ALIASES = {
    "ollama": "ollama",
    "lmstudio": "lmstudio",
    "lm-studio": "lmstudio",
    "lm_studio": "lmstudio",
    "mlx": "mlx",
    "openai": "openai",
    "gpt": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "mistral": "mistral",
    "devstral": "mistral",
    "openrouter": "openrouter",
    "http": "http",
    # CLI backends
    "claude-cli": "claude-cli",
    "claude_cli": "claude-cli",
    "claudecode": "claude-cli",
    "claude-code": "claude-cli",
    "codex": "codex",
    "codex-cli": "codex",
    "openai-cli": "codex",
    "gemini": "gemini",
    "gemini-cli": "gemini",
}

# Default URLs for each backend
DEFAULT_URLS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234",
}


def create_backend(config) -> LLMBackend:
    """
    Create an LLM backend based on configuration.

    Supported backends:
        API Backends:
        - anthropic: Anthropic Claude API (uses ANTHROPIC_API_KEY)
        - mistral: Mistral AI API (uses MISTRAL_API_KEY)
        - openai: OpenAI API (uses Replit AI Integrations or OPENAI_API_KEY)
        - openrouter: OpenRouter API (uses OPENROUTER_API_KEY) - 100+ models
        - ollama: Ollama local server (default: localhost:11434)
        - lmstudio: LM Studio local server (default: localhost:1234)
        - mlx: Native Apple Silicon with mlx-lm
        - http: Any OpenAI-compatible API (requires base_url)

        CLI Backends (use subscription credits):
        - claude-cli: Claude Code CLI (uses Claude Pro/Plus subscription)
        - codex: OpenAI Codex CLI (uses ChatGPT Pro/Plus subscription)
        - gemini: Google Gemini CLI (uses AI Studio credits)
    """
    backend_type = config.model.backend.lower()
    backend_type = BACKEND_ALIASES.get(backend_type, backend_type)

    # API backends
    if backend_type == "anthropic":
        return AnthropicBackend(model=config.model.name)

    elif backend_type == "mistral":
        return MistralBackend(model=config.model.name)

    elif backend_type == "openrouter":
        return OpenRouterBackend(model=config.model.name)

    elif backend_type == "ollama":
        base_url = config.model.base_url or DEFAULT_URLS["ollama"]
        return OllamaBackend(model=config.model.name, base_url=base_url)

    elif backend_type == "lmstudio":
        base_url = config.model.base_url or DEFAULT_URLS["lmstudio"]
        return LMStudioBackend(model=config.model.name, base_url=base_url)

    elif backend_type == "mlx":
        return MLXBackend(model=config.model.name)

    elif backend_type == "openai":
        return OpenAIBackend(model=config.model.name)

    elif backend_type == "http":
        if not config.model.base_url:
            raise ValueError("HTTP backend requires base_url in config")
        return OpenAICompatibleBackend(
            base_url=config.model.base_url,
            model=config.model.name
        )

    # CLI backends
    elif backend_type == "claude-cli":
        return ClaudeCodeCLIBackend(model=config.model.name)

    elif backend_type == "codex":
        return CodexCLIBackend(model=config.model.name)

    elif backend_type == "gemini":
        return GeminiCLIBackend(model=config.model.name)

    else:
        raise ValueError(
            f"Unknown backend: {backend_type}\n"
            f"Supported API backends: anthropic, mistral, openai, openrouter, ollama, lmstudio, mlx, http\n"
            f"Supported CLI backends: claude-cli, codex, gemini"
        )


def list_backends() -> str:
    """Return a formatted string describing available backends."""
    return """
Available LLM Backends:
=======================

API BACKENDS (use API keys):
-----------------------------

1. Anthropic Claude (best for complex tasks)
   Backend: anthropic
   Models: claude-3-5-sonnet-20241022 (recommended), claude-3-opus-20250219, claude-3-haiku-20240307
   Setup:
     1. Get API key from https://console.anthropic.com/
     2. export ANTHROPIC_API_KEY="your-key"
     3. Set in config: backend=anthropic, name=claude-3-5-sonnet-20241022

2. Mistral (fast, affordable coding models)
   Backend: mistral
   Models: devstral-small-2505 (24B, recommended), mistral-large-latest, etc.
   Setup:
     1. Get API key from https://console.mistral.ai/
     2. export MISTRAL_API_KEY="your-key"
     3. Set in config: backend=mistral, name=devstral-small-2505

3. OpenAI (great for Claude Code, Replit AI Integrations)
   Backend: openai
   Models: gpt-4o, gpt-4o-mini, gpt-4.1, o3-mini, etc.
   Uses Replit AI Integrations (no API key needed!)

4. OpenRouter (100+ models, one API key)
   Backend: openrouter
   Models: anthropic/claude-3.5-sonnet, google/gemini-2.0-flash-exp, openai/gpt-4-turbo,
           qwen/qwen-2.5-coder-32b-instruct, meta-llama/llama-3.1-405b-instruct, etc.
   Setup:
     1. Get API key from https://openrouter.ai/
     2. export OPENROUTER_API_KEY="your-key"
     3. Set in config: backend=openrouter, name=anthropic/claude-3.5-sonnet
   Note: Access to 100+ models including Claude, GPT-4, Gemini, Llama, and more!
         See full list: https://openrouter.ai/models

5. Ollama (local LLM server)
   Backend: ollama
   Default URL: http://localhost:11434
   Setup:
     brew install ollama
     ollama pull devstral
     ollama serve

6. LM Studio (great GUI, easy model management)
   Backend: lmstudio
   Default URL: http://localhost:1234
   Setup:
     1. Download from https://lmstudio.ai
     2. Load a coding model (Devstral, CodeLlama, etc.)
     3. Start local server

7. MLX (native Apple Silicon, fastest on Mac)
   Backend: mlx
   Requires: pip install mlx-lm
   Note: Model downloaded automatically on first run

8. HTTP (any OpenAI-compatible API)
   Backend: http
   Requires: base_url in config
   Works with: vLLM, text-generation-inference, etc.

CLI BACKENDS (use subscription credits):
-----------------------------------------
⚠️  WARNING: These backends use your Pro/Plus subscriptions!
⚠️  Autonomous agent loops can consume credits VERY QUICKLY!
⚠️  Only use CLI backends if you understand the cost implications!

9. Claude Code CLI (Anthropic Pro/Plus subscription)
   Backend: claude-cli
   Models: sonnet (recommended), opus, haiku
   Setup:
     1. Install from https://claude.com/code
     2. claude auth
     3. Set in config: backend=claude-cli, name=sonnet
   Features:
     - Uses -p flag for headless mode
     - Auto-approves tools with --dangerously-skip-permissions
     - Monitor usage: https://console.anthropic.com/

10. OpenAI Codex CLI (ChatGPT Pro/Plus subscription)
    Backend: codex
    Models: gpt-5-codex (recommended), gpt-5, gpt-4o
    Setup:
      1. Install: npm i -g @openai/codex OR brew install codex
      2. codex (authenticate on first run)
      3. Set in config: backend=codex, name=gpt-5-codex
    Features:
      - Uses ChatGPT Pro/Plus/Business subscription
      - Monitor usage in ChatGPT account settings

11. Google Gemini CLI (AI Studio credits)
    Backend: gemini
    Models: gemini-2.5-flash (recommended), gemini-2.5-pro, gemini-3-pro
    Setup:
      1. Install from https://github.com/google-gemini/gemini-cli
      2. gemini auth
      3. Set in config: backend=gemini, name=gemini-2.5-flash
    Features:
      - Uses -p flag for headless mode
      - Auto-approves with --yolo flag
      - Monitor usage: https://aistudio.google.com/

CHOOSING A BACKEND:
-------------------
- For API usage: Use 'anthropic', 'mistral', 'openai', or 'openrouter' for production
- For local development: Use 'ollama' or 'lmstudio'
- For Mac users: 'mlx' offers native Apple Silicon performance
- For CLI (Pro subscriptions): Use 'claude-cli', 'codex', or 'gemini'
  BUT BE AWARE: CLI usage will consume your subscription credits rapidly!
"""
