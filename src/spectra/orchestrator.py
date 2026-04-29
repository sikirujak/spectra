"""Pipeline Orchestrator — coordinates Scout → Analyst → Executor pipeline."""

from __future__ import annotations

import asyncio
import logging

from spectra.agents.analyst import AnalystAgent
from spectra.agents.executor import ExecutorAgent
from spectra.agents.scout import ScoutAgent
from spectra.config import SpectraConfig

logger = logging.getLogger("spectra.orchestrator")


class PipelineOrchestrator:
    """Orchestrates the full Scout → Analyst → Executor pipeline.

    Coordinates inter-agent communication and manages the lifecycle
    of each agent. Can run in continuous mode or single-pass mode.
    """

    def __init__(self, config: SpectraConfig) -> None:
        self.config = config
        self.scout = ScoutAgent(config)
        self.analyst = AnalystAgent(config)
        self.executor = ExecutorAgent(config)
        self._running = False

    async def run_single_pass(self) -> list:
        """Run a single pass through the full pipeline.

        1. Scout discovers signals
        2. Analyst assesses each signal
        3. Executor formats and delivers briefs

        Returns the list of Brief objects produced.
        """
        logger.info("Starting single-pass pipeline run")

        # Stage 1: Scout discovers signals
        logger.info("Stage 1: Scout — discovering signals")
        signals = await self.scout.run_cycle()
        logger.info(f"Scout found {len(signals)} signals")

        if not signals:
            logger.info("No signals discovered, pipeline complete")
            return []

        # Stage 2: Analyst assesses signals
        logger.info("Stage 2: Analyst — assessing signals")
        assessments = await self.analyst.analyze_batch(signals)
        logger.info(f"Analyst produced {len(assessments)} assessments")

        if not assessments:
            logger.info("No assessments produced, pipeline complete")
            return []

        # Stage 3: Executor delivers briefs
        logger.info("Stage 3: Executor — delivering briefs")
        briefs = await self.executor.process_batch(assessments)
        logger.info(f"Executor delivered {len(briefs)} briefs")

        return briefs

    async def run_continuous(self) -> None:
        """Run the pipeline continuously with periodic scan cycles."""
        self._running = True
        logger.info("Starting continuous pipeline mode")

        while self._running:
            try:
                briefs = await self.run_single_pass()
                if briefs:
                    logger.info(f"Pipeline cycle produced {len(briefs)} briefs")
            except Exception as e:
                logger.error(f"Pipeline cycle error: {e}")

            await asyncio.sleep(self.config.agent.scout_poll_interval)

        logger.info("Continuous pipeline stopped")

    async def run_daemon(self) -> None:
        """Run as a daemon with independent agent processes.

        In daemon mode, each agent runs as an independent async task,
        connected via Redis pub/sub channels for inter-agent communication.
        """
        self._running = True
        logger.info("Starting daemon mode with Redis pub/sub")

        # In production, each agent would subscribe to its Redis channel
        # and publish results to the next agent's channel
        # For now, we run the simplified continuous mode
        await self.run_continuous()

    def stop(self) -> None:
        """Stop all agents and the orchestrator."""
        self._running = False
        self.scout.stop()
        self.analyst.stop()
        self.executor.stop()
        logger.info("Orchestrator stopped all agents")


async def main(mode: str = "pipeline") -> None:
    """Entry point for running Spectra."""
    from spectra.config import get_config

    config = get_config()
    orchestrator = PipelineOrchestrator(config)

    if mode == "pipeline":
        briefs = await orchestrator.run_single_pass()
        print(f"\nPipeline complete: {len(briefs)} briefs generated")
        for brief in briefs:
            print(f"\n{brief.summary}\n")
    elif mode == "continuous":
        await orchestrator.run_continuous()
    elif mode == "daemon":
        await orchestrator.run_daemon()
    else:
        raise ValueError(f"Unknown mode: {mode}. Use pipeline/continuous/daemon.")


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    asyncio.run(main(mode))