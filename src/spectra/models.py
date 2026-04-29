"""Data models for Spectra pipeline."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class SignalType(str, enum.Enum):
    """Types of signals the Scout agent can discover."""
    NEW_LP = "new_lp"
    PRICE_SPIKE = "price_spike"
    VOLUME_SURGE = "volume_surge"
    WHALE_MOVE = "whale_move"
    SOCIAL_BUZZ = "social_buzz"
    ANNOUNCEMENT = "announcement"


class RiskLevel(str, enum.Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Signal(BaseModel):
    """A signal emitted by the Scout agent."""
    signal_id: str = Field(default_factory=lambda: f"sig_{int(datetime.now(timezone.utc).timestamp())}")
    signal_type: SignalType
    source: str
    chain: str = "unknown"
    token_address: Optional[str] = None
    token_name: Optional[str] = None
    data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Optional[dict] = None


class Assessment(BaseModel):
    """An assessment produced by the Analyst agent after reasoning."""
    assessment_id: str = Field(default_factory=lambda: f"asm_{int(datetime.now(timezone.utc).timestamp())}")
    signal_id: str
    token_name: Optional[str] = None
    token_address: Optional[str] = None
    chain: str = "unknown"
    confidence_score: int = Field(ge=0, le=100, description="0-100 confidence score")
    risk_level: RiskLevel = RiskLevel.MEDIUM
    reasoning_chain: list[str] = Field(default_factory=list, description="Step-by-step reasoning steps")
    fundamentals: dict = Field(default_factory=dict, description="Project fundamentals summary")
    onchain_summary: dict = Field(default_factory=dict, description="On-chain data summary")
    recommendation: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Brief(BaseModel):
    """An intelligence brief produced by the Executor agent."""
    brief_id: str = Field(default_factory=lambda: f"brf_{int(datetime.now(timezone.utc).timestamp())}")
    assessment_id: str
    title: str
    confidence_score: int
    risk_level: RiskLevel
    chain: str
    token_name: Optional[str] = None
    summary: str
    action: str
    delivered_to: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
