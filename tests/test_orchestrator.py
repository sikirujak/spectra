"""Tests for Pipeline Orchestrator."""

import pytest
from spectra.orchestrator import PipelineOrchestrator
from spectra.config import SpectraConfig


@pytest.fixture
def config():
    return SpectraConfig()


@pytest.fixture
def orchestrator(config):
    return PipelineOrchestrator(config)


def test_orchestrator_initialization(orchestrator):
    assert orchestrator.scout is not None
    assert orchestrator.analyst is not None
    assert orchestrator.executor is not None


def test_orchestrator_stop(orchestrator):
    orchestrator.stop()
    assert orchestrator._running is False