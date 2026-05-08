"""Model providers — OpenAI-compatible and Claude."""

import io
import logging
import sys
from typing import List

from .base import BaseModel, Message

logger = logging.getLogger(__name__)


class OpenAICompatibleModel(BaseModel):
    """Provider for OpenAI-compatible APIs (GPT, GLM, MiMo, DeepSeek, Qwen, LongCat, Kimi, Doubao, Yuanbao, Grok, etc.)."""

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
        content = response.choices[0].message.content
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return content

    def chat_stream(self, messages: List[Message], **kwargs):
        """Stream chat response, yields delta chunks."""
        client = self._get_client()
        stream = client.chat.completions.create(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class ClaudeModel(BaseModel):
    """Provider for Anthropic Claude API (official and proxy)."""

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

    def chat_stream(self, messages: List[Message], **kwargs):
        """Stream chat response, yields delta chunks."""
        client = self._get_client()
        system_content = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_content = m.content
            else:
                chat_messages.append(m.to_dict())
        with client.messages.stream(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            system=system_content if system_content else "",
            messages=chat_messages,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield text


# Provider registry
PROVIDER_REGISTRY = {
    # LongCat 系列（默认推荐）
    "longcat": OpenAICompatibleModel,
    "longcat-flash": OpenAICompatibleModel,
    "longcat-thinking": OpenAICompatibleModel,
    "longcat-omni": OpenAICompatibleModel,
    "longcat-lite": OpenAICompatibleModel,
    # OpenAI
    "openai": OpenAICompatibleModel,
    # 智谱 GLM
    "glm": OpenAICompatibleModel,
    # 小米 MiMo
    "mimo": OpenAICompatibleModel,
    # DeepSeek
    "deepseek": OpenAICompatibleModel,
    # 阿里通义千问
    "qwen": OpenAICompatibleModel,
    # 月之暗面 Kimi
    "kimi": OpenAICompatibleModel,
    # 字节跳动 豆包（火山方舟）
    "doubao": OpenAICompatibleModel,
    # 腾讯混元 元宝
    "yuanbao": OpenAICompatibleModel,
    # xAI Grok
    "grok": OpenAICompatibleModel,
    # 通用 OpenAI 兼容中转站
    "openai-proxy": OpenAICompatibleModel,
    # Anthropic Claude（官方）
    "claude": ClaudeModel,
    # 通用 Anthropic 兼容中转站
    "claude-proxy": ClaudeModel,
}


def create_model(provider: str, **kwargs) -> BaseModel:
    """Create a model instance by provider name."""
    cls = PROVIDER_REGISTRY.get(provider)
    if not cls:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDER_REGISTRY.keys())}")
    return cls(**kwargs)
