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


class OllamaBackend(LLMBackend):
    def __init__(self, model: str = "devstral", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=300.0)
    
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
        except Exception as e:
            return LLMResponse(
                content=f"Error calling Ollama: {str(e)}",
                usage=TokenUsage(),
                finish_reason="error"
            )


class MLXBackend(LLMBackend):
    def __init__(self, model: str = "mistralai/Devstral-Small-2-24B-Instruct"):
        self.model_name = model
        self._model = None
        self._tokenizer = None
    
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


class HTTPBackend(LLMBackend):
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
                content=message.get("content", ""),
                tool_calls=message.get("tool_calls", []),
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


def create_backend(config) -> LLMBackend:
    backend_type = config.model.backend.lower()
    
    if backend_type == "ollama":
        base_url = config.model.base_url or "http://localhost:11434"
        return OllamaBackend(model=config.model.name, base_url=base_url)
    elif backend_type == "mlx":
        return MLXBackend(model=config.model.name)
    elif backend_type == "http":
        if not config.model.base_url:
            raise ValueError("HTTP backend requires base_url")
        return HTTPBackend(
            base_url=config.model.base_url,
            model=config.model.name
        )
    else:
        raise ValueError(f"Unknown backend: {backend_type}")
