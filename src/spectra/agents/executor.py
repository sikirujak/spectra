"""Executor Agent — Output formatting and alert delivery.

The Executor agent is the final stage in the Spectra pipeline. It consumes
Assessment objects from the Analyst agent, formats them into human-readable
intelligence briefs, and delivers them via configured channels (Telegram,
Discord, JSON files).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from spectra.config import SpectraConfig
from spectra.models import Assessment, Brief, RiskLevel

logger = logging.getLogger("spectra.executor")


class BriefFormatter:
    """Formats assessments into structured intelligence briefs."""

    RISK_ICONS = {
        RiskLevel.LOW: "🟢",
        RiskLevel.MEDIUM: "🟡",
        RiskLevel.HIGH: "🔴",
        RiskLevel.CRITICAL: "⛔",
    }

    CONFIDENCE_TIERS = {
        (80, 100): "🔴 HIGH CONFIDENCE",
        (50, 79): "🟡 MODERATE CONFIDENCE",
        (0, 49): "⚪ LOW CONFIDENCE",
    }

    def format_brief(self, assessment: Assessment) -> Brief:
        """Convert an Assessment into a Brief with formatted content."""
        risk_icon = self.RISK_ICONS.get(assessment.risk_level, "⚪")
        tier = self._get_confidence_tier(assessment.confidence_score)

        reasoning_summary = "\n".join(
            f"  {i+1}. {step}" for i, step in enumerate(assessment.reasoning_chain[:5])
        )

        summary = f"""{risk_icon} {tier}

**Token:** {assessment.token_name or 'Unknown'}
**Chain:** {assessment.chain}
**Confidence:** {assessment.confidence_score}/100
**Risk:** {assessment.risk_level.value}

**Reasoning:**
{reasoning_summary}

**Recommendation:** {assessment.recommendation}"""

        action = self._determine_action(assessment)

        return Brief(
            assessment_id=assessment.assessment_id,
            title=f"{assessment.token_name or 'Unknown'} — {tier.split(' ', 1)[1]}",
            confidence_score=assessment.confidence_score,
            risk_level=assessment.risk_level,
            chain=assessment.chain,
            token_name=assessment.token_name,
            summary=summary,
            action=action,
        )

    def _get_confidence_tier(self, score: int) -> str:
        """Map confidence score to tier label."""
        for (low, high), label in self.CONFIDENCE_TIERS.items():
            if low <= score <= high:
                return label
        return "⚪ LOW CONFIDENCE"

    def _determine_action(self, assessment: Assessment) -> str:
        """Determine the recommended action based on assessment."""
        if assessment.confidence_score >= 80 and assessment.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
            return "IMMEDIATE — Act now, high confidence + acceptable risk"
        elif assessment.confidence_score >= 60:
            return "MONITOR — Watch for confirming signals"
        elif assessment.confidence_score >= 40:
            return "DIGEST — Include in periodic summary only"
        else:
            return "SKIP — Insufficient confidence or high risk"


class TelegramDelivery:
    """Delivers briefs via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base = "https://api.telegram.org/bot{token}"
        self._http = None

    async def send(self, brief: Brief) -> bool:
        """Send a brief as a Telegram message."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured, skipping delivery")
            return False

        import httpx
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30)

        url = self.api_base.format(token=self.bot_token) + "/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": brief.summary,
            "parse_mode": "Markdown",
        }

        try:
            resp = await self._http.post(url, json=payload)
            if resp.status_code == 200:
                logger.info(f"Brief delivered to Telegram: {brief.brief_id}")
                return True
            else:
                logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram delivery failed: {e}")
            return False

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()


class ExecutorAgent:
    """Output and alerting agent that delivers intelligence briefs."""

    def __init__(self, config: SpectraConfig) -> None:
        self.config = config
        self.formatter = BriefFormatter()
        self.telegram = TelegramDelivery(
            bot_token=config.output.telegram_bot_token,
            chat_id=config.output.telegram_chat_id,
        )
        self._running = False
        self._briefs: list[Brief] = []

    async def process_assessment(self, assessment: Assessment) -> Brief:
        """Process a single assessment into a brief and deliver it."""
        brief = self.formatter.format_brief(assessment)
        self._briefs.append(brief)

        # Deliver based on action tier
        if brief.action.startswith("IMMEDIATE") or brief.action.startswith("MONITOR"):
            await self.telegram.send(brief)
            brief.delivered_to.append("telegram")

        logger.info(f"Processed assessment → brief: {brief.brief_id} ({brief.action})")
        return brief

    async def process_batch(self, assessments: list[Assessment]) -> list[Brief]:
        """Process a batch of assessments."""
        briefs = []
        for assessment in assessments:
            brief = await self.process_assessment(assessment)
            briefs.append(brief)
        return briefs

    async def generate_digest(self) -> str:
        """Generate a periodic digest of all collected briefs."""
        if not self._briefs:
            return "No intelligence briefs to report."

        high_confidence = [b for b in self._briefs if b.confidence_score >= 70]
        medium_confidence = [b for b in self._briefs if 40 <= b.confidence_score < 70]
        low_confidence = [b for b in self._briefs if b.confidence_score < 40]

        digest_parts = [
            "📊 **Spectra Intelligence Digest**",
            f"Period: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
            f"Total signals processed: {len(self._briefs)}",
            "",
            f"🔴 High confidence: {len(high_confidence)}",
            f"🟡 Medium confidence: {len(medium_confidence)}",
            f"⚪ Low confidence: {len(low_confidence)}",
            "",
        ]

        for brief in high_confidence[:5]:
            digest_parts.append(f"• {brief.token_name or 'Unknown'} ({brief.chain}) — {brief.action}")

        digest = "\n".join(digest_parts)
        self._briefs.clear()
        return digest

    async def run(self, assessment_source: callable = None) -> None:
        """Run the Executor agent continuously."""
        import asyncio

        self._running = True
        logger.info("Executor agent started")

        while self._running:
            try:
                if assessment_source:
                    assessments = await assessment_source()
                    if assessments:
                        await self.process_batch(assessments)
            except Exception as e:
                logger.error(f"Executor cycle error: {e}")

            await asyncio.sleep(self.config.agent.executor_digest_interval)

        await self.telegram.close()
        logger.info("Executor agent stopped")

    def stop(self) -> None:
        """Stop the Executor agent."""
        self._running = False