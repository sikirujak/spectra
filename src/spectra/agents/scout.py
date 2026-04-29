"""Scout Agent — Signal discovery and data collection.

The Scout agent is the first stage in the Spectra pipeline. It monitors
multiple data sources in parallel and emits structured Signal objects
when it detects meaningful market events.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from spectra.config import SpectraConfig
from spectra.models import Signal, SignalType
from spectra.tools.dexscreener import DexScreenerClient
from spectra.tools.onchain import OnchainClient

logger = logging.getLogger("spectra.scout")


class ScoutAgent:
    """Signal discovery agent that monitors data sources and emits Signals."""

    def __init__(self, config: SpectraConfig) -> None:
        self.config = config
        self.dex = DexScreenerClient(config.data_source.dexscreener_api)
        self.onchain = OnchainClient()
        self._running = False

    async def scan_new_pools(self, chain: str = "solana") -> list[Signal]:
        """Scan for newly created liquidity pools on DEX."""
        logger.info(f"Scanning new pools on {chain}")
        try:
            results = await self.dex.get_new_pools(chain)
            signals = []
            for pool in results:
                signal = Signal(
                    signal_type=SignalType.NEW_LP,
                    source="dexscreener",
                    chain=chain,
                    token_address=pool.get("tokenAddress"),
                    token_name=pool.get("baseToken", {}).get("symbol", "unknown"),
                    data={
                        "liquidity_usd": pool.get("liquidity", {}).get("usd", 0),
                        "volume_24h": pool.get("volume", {}).get("h24", 0),
                        "price_change_24h": pool.get("priceChange", {}).get("h24", 0),
                    },
                    raw_payload=pool,
                )
                signals.append(signal)
                logger.info(f"Found new pool: {signal.token_name} ({signal.token_address})")
            return signals
        except Exception as e:
            logger.error(f"Error scanning new pools: {e}")
            return []

    async def scan_price_spikes(self, chain: str = "solana", threshold: float = 50.0) -> list[Signal]:
        """Scan for tokens with significant price changes."""
        logger.info(f"Scanning price spikes on {chain} (threshold: {threshold}%)")
        try:
            results = await self.dex.get_trending_tokens(chain)
            signals = []
            for token in results:
                price_change = token.get("priceChange", {}).get("h24", 0)
                if abs(price_change) >= threshold:
                    signal = Signal(
                        signal_type=SignalType.PRICE_SPIKE,
                        source="dexscreener",
                        chain=chain,
                        token_address=token.get("tokenAddress"),
                        token_name=token.get("baseToken", {}).get("symbol", "unknown"),
                        data={
                            "price_change_pct": price_change,
                            "volume_24h": token.get("volume", {}).get("h24", 0),
                        },
                        raw_payload=token,
                    )
                    signals.append(signal)
                    logger.info(f"Price spike detected: {signal.token_name} ({price_change:.1f}%)")
            return signals
        except Exception as e:
            logger.error(f"Error scanning price spikes: {e}")
            return []

    async def scan_whale_moves(self, chain: str = "solana") -> list[Signal]:
        """Scan for large on-chain transactions (whale movements)."""
        logger.info(f"Scanning whale movements on {chain}")
        try:
            results = await self.onchain.get_large_transactions(chain)
            signals = []
            for tx in results:
                signal = Signal(
                    signal_type=SignalType.WHALE_MOVE,
                    source="onchain_rpc",
                    chain=chain,
                    token_address=tx.get("token_address"),
                    token_name=tx.get("token_symbol", "unknown"),
                    data={
                        "amount": tx.get("amount", 0),
                        "usd_value": tx.get("usd_value", 0),
                        "direction": tx.get("direction", "unknown"),
                    },
                    raw_payload=tx,
                )
                if signal.data.get("usd_value", 0) > 100000:
                    signals.append(signal)
                    logger.info(
                        f"Whale move: {signal.data['direction']} "
                        f"${signal.data['usd_value']:,.0f} of {signal.token_name}"
                    )
            return signals
        except Exception as e:
            logger.error(f"Error scanning whale moves: {e}")
            return []

    async def run_cycle(self) -> list[Signal]:
        """Run a full scan cycle across all data sources."""
        all_signals: list[Signal] = []
        tasks = [
            self.scan_new_pools(),
            self.scan_price_spikes(),
            self.scan_whale_moves(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_signals.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Scan task failed: {result}")
        logger.info(f"Scan cycle complete: {len(all_signals)} signals discovered")
        return all_signals

    async def run(self, callback: callable = None) -> None:
        """Run the Scout agent continuously."""
        self._running = True
        logger.info("Scout agent started")
        while self._running:
            signals = await self.run_cycle()
            if callback and signals:
                await callback(signals)
            await asyncio.sleep(self.config.agent.scout_poll_interval)
        logger.info("Scout agent stopped")

    def stop(self) -> None:
        """Stop the Scout agent."""
        self._running = False