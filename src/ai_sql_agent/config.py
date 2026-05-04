"""Configuration management for multi-model AI SQL Agent."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class ModelProvider:
    """Single model provider config."""
    name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.3


@dataclass
class AgentConfig:
    """Agent workflow configuration."""
    default_provider: str = field(default_factory=lambda: os.getenv("AI_DEFAULT_PROVIDER", "openai"))
    max_retries: int = 3
    max_sub_tasks: int = 5
    execution_timeout: int = 30


@dataclass
class DBConfig:
    """Database connection config."""
    db_type: Optional[str] = field(default_factory=lambda: os.getenv("DB_TYPE"))
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5236")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", ""))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.db_type and self.name)


# --- Provider presets ---

PROVIDER_PRESETS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
    },
    "mimo": {
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5",
    },
    "claude": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-20250514",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
}


def build_provider(name: str, api_key: Optional[str] = None) -> ModelProvider:
    """Build a ModelProvider from preset + env vars."""
    preset = PROVIDER_PRESETS.get(name, {})
    env_key = f"AI_{name.upper()}_API_KEY"
    env_url = f"AI_{name.upper()}_BASE_URL"
    env_model = f"AI_{name.upper()}_MODEL"
    return ModelProvider(
        name=name,
        api_key=api_key or os.getenv(env_key, ""),
        base_url=os.getenv(env_url, preset.get("base_url", "")),
        model=os.getenv(env_model, preset.get("model", "")),
    )
