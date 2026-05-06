"""Configuration management for multi-model AI SQL Agent."""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from pathlib import Path

# Load .env.local first (local secrets, git-ignored), then .env as fallback
_env_local = Path(__file__).resolve().parent.parent.parent / ".env.local"
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_local.exists():
    load_dotenv(str(_env_local))
elif _env_file.exists():
    load_dotenv(str(_env_file))


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
    default_provider: str = field(default_factory=lambda: os.getenv("AI_DEFAULT_PROVIDER", "longcat"))
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


def _env_key(name: str, suffix: str) -> str:
    """Convert provider name to env var prefix.
    e.g. 'longcat-flash' -> 'AI_LONGCAT_FLASH_'
    """
    return f"AI_{name.upper().replace('-', '_').replace('.', '_')}{suffix}"


# --- Provider presets ---

PROVIDER_PRESETS = {
    # LongCat 系列（默认推荐）
    "longcat": {
        "base_url": "https://api.longcat.chat/openai",
        "model": "longcat-2.0-preview",
    },
    "longcat-flash": {
        "base_url": "https://api.longcat.chat/openai",
        "model": "LongCat-Flash-Chat",
    },
    "longcat-thinking": {
        "base_url": "https://api.longcat.chat/openai",
        "model": "LongCat-Flash-Thinking-2601",
    },
    "longcat-omni": {
        "base_url": "https://api.longcat.chat/openai",
        "model": "LongCat-Flash-Omni-2603",
    },
    "longcat-lite": {
        "base_url": "https://api.longcat.chat/openai",
        "model": "LongCat-Flash-Lite",
    },
    # OpenAI
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    # 智谱 GLM
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
    },
    # 小米 MiMo
    "mimo": {
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5",
    },
    # Anthropic Claude
    "claude": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-20250514",
    },
    # DeepSeek
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    # 阿里通义千问
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    # 月之暗面 Kimi
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.6",
    },
    # 字节跳动 豆包（火山方舟）
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
    },
    # 腾讯混元 元宝
    "yuanbao": {
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-turbo",
    },
    # xAI Grok
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-4-1-fast",
    },
    # 通用 OpenAI 兼容中转站（如 One-API、New-API 等）
    "openai-proxy": {
        "base_url": "",
        "model": "",
    },
    # 通用 Anthropic 兼容中转站
    "claude-proxy": {
        "base_url": "",
        "model": "",
    },
}


def build_provider(name: str, api_key: Optional[str] = None) -> ModelProvider:
    """Build a ModelProvider from preset + env vars."""
    preset = PROVIDER_PRESETS.get(name, {})
    env_key = _env_key(name, "_API_KEY")
    env_url = _env_key(name, "_BASE_URL")
    env_model = _env_key(name, "_MODEL")
    return ModelProvider(
        name=name,
        api_key=api_key or os.getenv(env_key, ""),
        base_url=os.getenv(env_url, preset.get("base_url", "")),
        model=os.getenv(env_model, preset.get("model", "")),
    )
