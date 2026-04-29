"""Analyst Agent — Deep reasoning and signal assessment.

The Analyst agent is the second stage in the Spectra pipeline. It consumes
Signal objects from the Scout agent, performs multi-step chain-of-thought
reasoning using LLMs (MiMo primary, Claude fallback), and outputs
scored Assessment objects.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from spectra.config import SpectraConfig
from spectra.models import Assessment, RiskLevel, Signal
from spectra.tools.llm import LLMClient

logger = logging.getLogger("spectra.analyst")

ANALYSIS_SYSTEM_PROMPT = """You are a crypto market analyst AI. Your job is to assess trading signals
using structured chain-of-thought reasoning.

For each signal, you MUST follow these steps in order:
1. **Verify**: Is the signal data consistent and plausible?
2. **Fundamentals**: What does the project do? Is the team known? Any red flags?
3. **On-chain check**: Look at holder distribution, LP lock, dev wallet share.
4. **Timing**: How fresh is this signal? Is it too late to act?
5. **Risk**: What could go wrong? Rate risk as LOW/MEDIUM/HIGH/CRITICAL.
6. **Score**: Assign a confidence score 0-100.

Output your analysis as JSON with these fields:
- reasoning_steps: list of step-by-step reasoning strings
- confidence_score: integer 0-100
- risk_level: LOW/MEDIUM/HIGH/CRITICAL
- fundamentals: object with project_name, category, team_known, red_flags
- onchain_summary: object with holder_concentration, lp_locked, dev_share
- recommendation: one-line actionable recommendation
"""


class AnalystAgent:
    """Deep reasoning agent that assesses signals using LLM chain-of-thought."""

    def __init__(self, config: SpectraConfig) -> None:
        self.config = config
        self.llm = LLMClient(
            api_key=config.llm.mimo_api_key,
            base_url=config.llm.mimo_base_url,
            model=config.llm.mimo_model,
            fallback_api_key=config.llm.claude_api_key,
            fallback_model=config.llm.claude_model,
        )
        self._running = False

    async def analyze_signal(self, signal: Signal) -> Assessment:
        """Perform deep analysis on a single signal using chain-of-thought reasoning."""
        logger.info(f"Analyzing signal: {signal.signal_id} ({signal.signal_type.value})")

        prompt = f"""Analyze this crypto market signal:

Signal Type: {signal.signal_type.value}
Source: {signal.source}
Chain: {signal.chain}
Token: {signal.token_name} ({signal.token_address})
Data: {json.dumps(signal.data, indent=2)}
Timestamp: {signal.timestamp.isoformat()}

Provide a thorough chain-of-thought analysis following the 6-step framework."""

        try:
            response = await self.llm.chat(
                system=ANALYSIS_SYSTEM_PROMPT,
                user=prompt,
                response_format="json",
            )
            result = self._parse_analysis(response, signal)
            logger.info(
                f"Analysis complete: {signal.token_name} → "
                f"score={result.confidence_score}, risk={result.risk_level.value}"
            )
            return result
        except Exception as e:
            logger.error(f"Analysis failed for {signal.signal_id}: {e}")
            return self._fallback_assessment(signal, str(e))

    def _parse_analysis(self, response: str, signal: Signal) -> Assessment:
        """Parse the LLM JSON response into an Assessment object."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
            else:
                raise ValueError("Could not parse LLM response as JSON")

        return Assessment(
            signal_id=signal.signal_id,
            token_name=signal.token_name,
            token_address=signal.token_address,
            chain=signal.chain,
            confidence_score=int(data.get("confidence_score", 50)),
            risk_level=RiskLevel(data.get("risk_level", "MEDIUM").lower()),
            reasoning_chain=data.get("reasoning_steps", []),
            fundamentals=data.get("fundamentals", {}),
            onchain_summary=data.get("onchain_summary", {}),
            recommendation=data.get("recommendation", "Insufficient data for recommendation"),
        )

    def _fallback_assessment(self, signal: Signal, error: str) -> Assessment:
        """Create a minimal assessment when LLM analysis fails."""
        return Assessment(
            signal_id=signal.signal_id,
            token_name=signal.token_name,
            token_address=signal.token_address,
            chain=signal.chain,
            confidence_score=0,
            risk_level=RiskLevel.CRITICAL,
            reasoning_chain=[f"Analysis failed: {error}"],
            recommendation="Skipping — analysis engine unavailable",
        )

    async def analyze_batch(self, signals: list[Signal]) -> list[Assessment]:
        """Analyze a batch of signals concurrently."""
        logger.info(f"Analyzing batch of {len(signals)} signals")
        tasks = [self.analyze_signal(s) for s in signals]
        assessments = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for a in assessments:
            if isinstance(a, Assessment):
                results.append(a)
            else:
                logger.error(f"Batch analysis task failed: {a}")
        return results

    async def run(self, signal_source: callable, assessment_sink: callable = None) -> None:
        """Run the Analyst agent continuously, consuming signals from the source."""
        import asyncio

        self._running = True
        logger.info("Analyst agent started")
        while self._running:
            try:
                signals = await signal_source()
                if signals:
                    assessments = await self.analyze_batch(signals)
                    if assessment_sink and assessments:
                        await assessment_sink(assessments)
            except Exception as e:
                logger.error(f"Analyst cycle error: {e}")
            await asyncio.sleep(5)
        logger.info("Analyst agent stopped")

    def stop(self) -> None:
        """Stop the Analyst agent."""
        self._running = False