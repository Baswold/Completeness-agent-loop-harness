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
    "http": "openai",
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
        - ollama: Ollama local server (default: localhost:11434)
        - lmstudio: LM Studio local server (default: localhost:1234)
        - mlx: Native Apple Silicon with mlx-lm
        - openai/http: Any OpenAI-compatible API
    """
    backend_type = config.model.backend.lower()
    backend_type = BACKEND_ALIASES.get(backend_type, backend_type)
    
    if backend_type == "ollama":
        base_url = config.model.base_url or DEFAULT_URLS["ollama"]
        return OllamaBackend(model=config.model.name, base_url=base_url)
    
    elif backend_type == "lmstudio":
        base_url = config.model.base_url or DEFAULT_URLS["lmstudio"]
        return LMStudioBackend(model=config.model.name, base_url=base_url)
    
    elif backend_type == "mlx":
        return MLXBackend(model=config.model.name)
    
    elif backend_type == "openai":
        if not config.model.base_url:
            raise ValueError("OpenAI-compatible backend requires base_url in config")
        return OpenAICompatibleBackend(
            base_url=config.model.base_url,
            model=config.model.name
        )
    
    else:
        raise ValueError(
            f"Unknown backend: {backend_type}\n"
            f"Supported: ollama, lmstudio, mlx, openai"
        )


def list_backends() -> str:
    """Return a formatted string describing available backends."""
    return """
Available LLM Backends:
=======================

1. Ollama (recommended for easy setup)
   Backend: ollama
   Default URL: http://localhost:11434
   Setup:
     brew install ollama
     ollama pull devstral
     ollama serve

2. LM Studio (great GUI, easy model management)
   Backend: lmstudio
   Default URL: http://localhost:1234
   Setup:
     1. Download from https://lmstudio.ai
     2. Load a coding model (Devstral, CodeLlama, etc.)
     3. Start local server

3. MLX (native Apple Silicon, fastest on Mac)
   Backend: mlx
   Requires: pip install mlx-lm
   Note: Model downloaded automatically on first run

4. OpenAI-compatible (any compatible API)
   Backend: openai
   Requires: base_url in config
   Works with: vLLM, text-generation-inference, etc.
"""
