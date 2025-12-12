import json
import httpx
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
    "mistral": "mistral",
    "devstral": "mistral",
    "http": "http",
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
        - mistral: Mistral AI API (uses MISTRAL_API_KEY)
        - openai: OpenAI API (uses Replit AI Integrations or OPENAI_API_KEY)
        - ollama: Ollama local server (default: localhost:11434)
        - lmstudio: LM Studio local server (default: localhost:1234)
        - mlx: Native Apple Silicon with mlx-lm
        - http: Any OpenAI-compatible API (requires base_url)
    """
    backend_type = config.model.backend.lower()
    backend_type = BACKEND_ALIASES.get(backend_type, backend_type)

    if backend_type == "mistral":
        return MistralBackend(model=config.model.name)

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

    else:
        raise ValueError(
            f"Unknown backend: {backend_type}\n"
            f"Supported: mistral, openai, ollama, lmstudio, mlx, http"
        )


def list_backends() -> str:
    """Return a formatted string describing available backends."""
    return """
Available LLM Backends:
=======================

1. Mistral (RECOMMENDED - fast, affordable coding models)
   Backend: mistral
   Models: devstral-small-2505 (24B, recommended), mistral-large-latest, etc.
   Setup:
     1. Get API key from https://console.mistral.ai/
     2. export MISTRAL_API_KEY="your-key"
     3. Set in config: backend=mistral, name=devstral-small-2505

2. OpenAI (great for Claude Code, Replit AI Integrations)
   Backend: openai
   Models: gpt-4o, gpt-4o-mini, gpt-4.1, o3-mini, etc.
   Uses Replit AI Integrations (no API key needed!)

3. Ollama (local LLM server)
   Backend: ollama
   Default URL: http://localhost:11434
   Setup:
     brew install ollama
     ollama pull devstral
     ollama serve

4. LM Studio (great GUI, easy model management)
   Backend: lmstudio
   Default URL: http://localhost:1234
   Setup:
     1. Download from https://lmstudio.ai
     2. Load a coding model (Devstral, CodeLlama, etc.)
     3. Start local server

5. MLX (native Apple Silicon, fastest on Mac)
   Backend: mlx
   Requires: pip install mlx-lm
   Note: Model downloaded automatically on first run

6. HTTP (any OpenAI-compatible API)
   Backend: http
   Requires: base_url in config
   Works with: vLLM, text-generation-inference, etc.
"""
