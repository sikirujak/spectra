"""Tests for Scout agent."""

import pytest
from spectra.agents.scout import ScoutAgent
from spectra.config import SpectraConfig
from spectra.models import Signal, SignalType


@pytest.fixture
def config():
    return SpectraConfig()


@pytest.fixture
def scout(config):
    return ScoutAgent(config)


def test_scout_initialization(scout):
    assert scout.config is not None
    assert scout.dex is not None
    assert scout.onchain is not None


def test_signal_creation():
    signal = Signal(
        signal_type=SignalType.NEW_LP,
        source="dexscreener",
        chain="solana",
        token_name="TEST",
        data={"liquidity_usd": 50000},
    )
    assert signal.signal_type == SignalType.NEW_LP
    assert signal.chain == "solana"
    assert signal.token_name == "TEST"
    assert signal.data["liquidity_usd"] == 50000