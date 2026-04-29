"""Tests for Analyst agent."""

import pytest
from spectra.agents.analyst import AnalystAgent
from spectra.config import SpectraConfig
from spectra.models import Assessment, RiskLevel, Signal, SignalType


@pytest.fixture
def config():
    return SpectraConfig()


@pytest.fixture
def analyst(config):
    return AnalystAgent(config)


def test_analyst_initialization(analyst):
    assert analyst.config is not None
    assert analyst.llm is not None


def test_fallback_assessment(analyst):
    signal = Signal(
        signal_type=SignalType.PRICE_SPIKE,
        source="dexscreener",
        chain="solana",
        token_name="TESTCOIN",
        data={"price_change_pct": 150.0},
    )
    assessment = analyst._fallback_assessment(signal, "LLM unavailable")
    assert assessment.confidence_score == 0
    assert assessment.risk_level == RiskLevel.CRITICAL
    assert assessment.token_name == "TESTCOIN"


def test_parse_analysis_response():
    """Test parsing a valid JSON response from the LLM."""
    analyst = AnalystAgent(SpectraConfig())
    response = """{
        "reasoning_steps": ["Signal verified", "Team is known"],
        "confidence_score": 75,
        "risk_level": "MEDIUM",
        "fundamentals": {"project_name": "TestProject"},
        "onchain_summary": {"holder_concentration": "moderate"},
        "recommendation": "Monitor for confirming signals"
    }"""
    signal = Signal(
        signal_type=SignalType.NEW_LP,
        source="dexscreener",
        chain="solana",
    )
    assessment = analyst._parse_analysis(response, signal)
    assert assessment.confidence_score == 75
    assert assessment.risk_level == RiskLevel.MEDIUM
    assert len(assessment.reasoning_chain) == 2