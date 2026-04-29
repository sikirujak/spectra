"""Configuration management for Spectra."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    mimo_api_key: str = os.getenv("MIMO_API_KEY", "")
    mimo_base_url: str = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    mimo_model: str = os.getenv("ANALYST_MODEL", "xiaomi/mimo-v2-pro")
    claude_api_key: str = os.getenv("CLAUDE_API_KEY", "")
    claude_model: str = "claude-sonnet-4"


@dataclass
class RedisConfig:
    """Redis message bus configuration."""
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    signal_channel: str = "spectra:signals"
    assessment_channel: str = "spectra:assessments"


@dataclass
class DataSourceConfig:
    """External data source configuration."""
    dexscreener_api: str = os.getenv("DEXSCREENER_API", "https://api.dexscreener.com/latest")


@dataclass
class OutputConfig:
    """Output channel configuration."""
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "")


@dataclass
class AgentConfig:
    """Individual agent settings."""
    scout_poll_interval: int = int(os.getenv("SCOUT_POLL_INTERVAL", "30"))
    executor_digest_interval: int = int(os.getenv("EXECUTOR_DIGEST_INTERVAL", "3600"))


@dataclass
class SpectraConfig:
    """Top-level configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


def get_config() -> SpectraConfig:
    """Get the application configuration."""
    return SpectraConfig()
