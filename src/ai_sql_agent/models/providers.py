"""Model providers — OpenAI-compatible and Claude."""

import logging
from typing import List

from .base import BaseModel, Message

logger = logging.getLogger(__name__)


class OpenAICompatibleModel(BaseModel):
    """Provider for OpenAI-compatible APIs (GPT, GLM, MiMo, DeepSeek, Qwen, etc.)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def chat(self, messages: List[Message], **kwargs) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
        )
        return response.choices[0].message.content


class ClaudeModel(BaseModel):
    """Provider for Anthropic Claude API."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def chat(self, messages: List[Message], **kwargs) -> str:
        client = self._get_client()
        # Extract system message
        system_content = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_content = m.content
            else:
                chat_messages.append(m.to_dict())
        response = client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            system=system_content if system_content else anthropic.NOT_GIVEN,
            messages=chat_messages,
        )
        return response.content[0].text


# Provider registry
PROVIDER_REGISTRY = {
    "openai": OpenAICompatibleModel,
    "glm": OpenAICompatibleModel,
    "mimo": OpenAICompatibleModel,
    "deepseek": OpenAICompatibleModel,
    "qwen": OpenAICompatibleModel,
    "longcat": OpenAICompatibleModel,
    "longcat-flash": OpenAICompatibleModel,
    "longcat-thinking": OpenAICompatibleModel,
    "longcat-omni": OpenAICompatibleModel,
    "longcat-lite": OpenAICompatibleModel,
    "claude": ClaudeModel,
}


def create_model(provider: str, **kwargs) -> BaseModel:
    """Create a model instance by provider name."""
    cls = PROVIDER_REGISTRY.get(provider)
    if not cls:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDER_REGISTRY.keys())}")
    return cls(**kwargs)
