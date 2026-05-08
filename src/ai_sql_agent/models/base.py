"""Base model interface for unified LLM access."""

from abc import ABC, abstractmethod
from typing import List, Optional, Iterator


class Message:
    """Chat message."""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class BaseModel(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, api_key: str, base_url: str, model: str,
                 max_tokens: int = 4096, temperature: float = 0.3):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    def chat(self, messages: List[Message], **kwargs) -> str:
        """Send messages and get response."""
        ...

    def chat_stream(self, messages: List[Message], **kwargs) -> Iterator[str]:
        """Stream chat response, yields delta chunks. Override for streaming support."""
        # Default fallback: non-streaming
        yield self.chat(messages, **kwargs)

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__

    def validate(self):
        if not self.api_key:
            raise ValueError(f"API key is required for {self.provider_name}")
